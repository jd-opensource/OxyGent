from __future__ import annotations

import logging
from typing import Any

from app.embedder import Embedder
from app.storage.es_client import ESClient
from app.storage.vearch_client import VearchClient, vearch_space_name

logger = logging.getLogger("oxybank.retrieval_service")


# ---------------------------------------------------------------------------
# Condition type classification
# ---------------------------------------------------------------------------

# Conditions whose search_type indicates a vector similarity search
_VECTOR_TYPES = {"vector", "semantic", "embedding"}

# Conditions that map to Elasticsearch structured queries
_ES_TYPES = {"exact", "term", "in", "terms", "fuzzy", "match"}


def _is_vector_condition(cond: dict) -> bool:
    mode = cond.get("mode", cond.get("search_type", "")).lower()
    return mode in _VECTOR_TYPES


def _is_es_condition(cond: dict) -> bool:
    mode = cond.get("mode", cond.get("search_type", "")).lower()
    return mode in _ES_TYPES


# ---------------------------------------------------------------------------
# ES query building
# ---------------------------------------------------------------------------

def _build_es_clause(cond: dict) -> dict:
    """Convert a single search condition into an ES query clause."""
    search_type = cond.get("mode", cond.get("search_type", "exact")).lower()
    field = cond.get("field", "")
    value = cond.get("value")

    if search_type in ("exact", "term"):
        return {"term": {field: value}}
    elif search_type in ("in", "terms"):
        values = value if isinstance(value, list) else [value]
        return {"terms": {field: values}}
    elif search_type in ("fuzzy", "match"):
        return {"match": {field: {"query": value, "fuzziness": "AUTO"}}}
    else:
        # Default to term match
        return {"term": {field: value}}


def _build_es_query(conditions: list[dict]) -> dict:
    """Build a bool query from multiple ES conditions."""
    if len(conditions) == 1:
        return _build_es_clause(conditions[0])
    return {"bool": {"must": [_build_es_clause(c) for c in conditions]}}


# ---------------------------------------------------------------------------
# Main retrieval logic
# ---------------------------------------------------------------------------

def execute_retrieval(
    es: ESClient,
    vearch: VearchClient,
    embedder,
    bank_id: str,
    api_def: dict,
    query_data: dict,
) -> dict:
    """Execute a retrieval against a bank based on an API definition.

    Parameters
    ----------
    query_data : dict
        Contains: conditions (field->value), page_size, page_number, top_k.

    Returns
    -------
    dict with keys: items, total, page_size, page_number
    """
    search_conditions: list[dict] = api_def.get("search_conditions", [])
    output_fields: list[str] = api_def.get("output_fields", [])
    user_conditions: dict = query_data.get("conditions", {})
    page_size: int = query_data.get("page_size", 10)
    page_number: int = query_data.get("page_number", 1)
    top_k: int = query_data.get("top_k", page_size)

    # Separate conditions by type, only include conditions that user provided a value for
    es_conditions: list[dict] = []
    vector_conditions: list[dict] = []

    for cond in search_conditions:
        field = cond.get("field", "")
        mode = cond.get("mode", "exact")
        value = user_conditions.get(field)
        if value is None or value == "":
            continue
        resolved = {"field": field, "mode": mode, "value": value}
        if _is_vector_condition(resolved):
            vector_conditions.append(resolved)
        elif _is_es_condition(resolved):
            es_conditions.append(resolved)

    # If no conditions provided at all, return paginated list of all samples
    if not es_conditions and not vector_conditions:
        from_ = (page_number - 1) * page_size
        result = es.search(
            f"samples_{bank_id}",
            query=None,
            size=page_size,
            from_=from_,
            source=output_fields or None,
        )
        return {
            "items": _project_fields(result.get("items", []), output_fields),
            "total": result.get("total", 0),
            "page_size": page_size,
            "page_number": page_number,
        }

    # Step 1: If only ES conditions (no vector), query ES directly
    if es_conditions and not vector_conditions:
        es_query = _build_es_query(es_conditions)
        from_ = (page_number - 1) * page_size
        result = es.search(
            f"samples_{bank_id}",
            query=es_query,
            size=page_size,
            from_=from_,
            source=output_fields or None,
        )
        return {
            "items": _project_fields(result.get("items", []), output_fields),
            "total": result.get("total", 0),
            "page_size": page_size,
            "page_number": page_number,
        }

    # Step 2: Vector search (with optional Vearch-native filter)
    vector_results: list[dict] = []
    if vector_conditions:
        # Build one Vearch sum entry per vector condition. Each condition contributes its
        # own {field}_vector column and query embedding; Vearch sums the distances.
        sum_entries: list[dict] = []
        for vc in vector_conditions:
            value = vc.get("value")
            field = vc.get("field", "")
            if value is None or str(value).strip() == "" or not field:
                continue
            emb = embedder.encode([str(value)])[0].tolist()
            vector_field = field if field.endswith("_vector") else f"{field}_vector"
            sum_entries.append({"field": vector_field, "feature": [float(x) for x in emb]})

        if not sum_entries:
            # No usable vector queries -> fall back to no-condition list
            from_ = (page_number - 1) * page_size
            result = es.search(
                f"samples_{bank_id}",
                query=None,
                size=page_size,
                from_=from_,
                source=output_fields or None,
            )
            return {
                "items": _project_fields(result.get("items", []), output_fields),
                "total": result.get("total", 0),
                "page_size": page_size,
                "page_number": page_number,
            }

        # sys_ filter fields now live in Vearch (see bank_service._collect_sys_filter_fields),
        # so we can pass every es_condition — including sys_status — as a Vearch native filter.
        filter_clauses: list[dict] | None = None
        if es_conditions:
            clauses = []
            for cond in es_conditions:
                field = cond.get("field", "")
                value = cond.get("value")
                mode = cond.get("mode", "exact")
                if mode in ("exact", "term"):
                    clauses.append({"term": {field: [value] if not isinstance(value, list) else value}})
                elif mode in ("in", "terms"):
                    vals = value if isinstance(value, list) else [value]
                    clauses.append({"term": {field: vals}})
            if clauses:
                filter_clauses = clauses

        space_name = vearch_space_name(bank_id)
        vector_results = vearch.search_multi(
            space_name,
            sum_entries=sum_entries,
            top_k=top_k,
            filter_clauses=filter_clauses,
            fields=None,
        )

    # Step 4: Enrich vector results from ES (Vearch only stores vectors + filter, not full docs)
    if vector_results:
        sample_ids = [r.get("sys_sample_id", r.get("_id", "")) for r in vector_results]
        es_docs = {}
        for sid in sample_ids:
            doc = es.get_doc(f"samples_{bank_id}", sid)
            if doc:
                es_docs[sid] = doc
        enriched = []
        for r in vector_results:
            sid = r.get("sys_sample_id", r.get("_id", ""))
            merged = dict(es_docs.get(sid, {}))
            merged["_score"] = r.get("_score", 0)
            enriched.append(merged)
        vector_results = enriched

    # Step 5: Apply pagination to vector results
    all_results = vector_results
    total = len(all_results)
    start = (page_number - 1) * page_size
    end = start + page_size
    paged = all_results[start:end]

    return {
        "items": _project_fields(paged, output_fields),
        "total": total,
        "page_size": page_size,
        "page_number": page_number,
    }


def _project_fields(results: list[dict], output_fields: list[str]) -> list[dict]:
    """Project only the requested output fields from each result."""
    if not output_fields:
        return results
    projected = []
    for item in results:
        row = {}
        for field in output_fields:
            if field in item:
                row[field] = item[field]
        # Always include id and score if present
        if "id" in item:
            row["id"] = item["id"]
        elif "_id" in item:
            row["id"] = item["_id"]
        if "_score" in item:
            row["_score"] = item["_score"]
        projected.append(row)
    return projected
