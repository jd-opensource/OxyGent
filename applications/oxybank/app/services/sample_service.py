from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.event_bus import EventBus, SampleStatusEvent
from app.storage.es_client import ESClient
from app.storage.vearch_client import VearchClient, vearch_space_name

logger = logging.getLogger("oxybank.sample_service")


# Canonical status assigned to freshly-deposited samples. The exact string is
# arbitrary from the backend's perspective (sys_status is a keyword-typed string
# with no enum enforcement) — it just needs to be consistent across every write
# path so the annotation-page filter and progress bar don't fragment. We use
# English tokens because they're also the canonical values shown in the agent
# Trigger Status dropdown.
DEFAULT_SAMPLE_STATUS = "Imported"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_vearch_field_config(es: ESClient, bank_id: str) -> dict:
    """Return dict with keys:
    - filter_fields: set of string filter fields stored in Vearch (custom + sys_ referenced).
    - vector_fields: set of custom field names that have a {field}_vector column in Vearch.
    - has_sys_chunk: whether Vearch stores sys_chunk_vector.
    """
    bank = es.get_doc("banks", bank_id)
    if not bank:
        return {"filter_fields": set(), "vector_fields": set(), "has_sys_chunk": False,
                "embedding_backend": "triton", "embedding_model": ""}

    from app.services.bank_service import (
        _collect_vector_fields as _cvf,
        _collect_sys_filter_fields as _csf,
    )
    retrieval_apis = bank.get("retrieval_apis", [])

    # Custom (non-sys_) filter fields — same logic as _build_vearch_properties
    custom_filter: set[str] = set()
    for api_def in retrieval_apis:
        if api_def.get("is_default"):
            continue
        for cond in api_def.get("search_conditions", []):
            f = cond.get("field", "")
            if f and cond.get("mode", "") != "vector" and not f.startswith("sys_"):
                custom_filter.add(f)
    # Also text-type schema fields go to Vearch as filter columns
    schema_fields = bank.get("schema", {}).get("fields", [])
    for field in schema_fields:
        name = field.get("name", "")
        if not name or name == "sys_chunk":
            continue
        if name in custom_filter or field.get("type") == "text":
            custom_filter.add(name)

    sys_filter = _csf(retrieval_apis)
    return {
        "filter_fields": custom_filter | sys_filter,
        "vector_fields": _cvf(retrieval_apis),
        "has_sys_chunk": bool(bank.get("has_sys_chunk", False)),
        "embedding_backend": bank.get("embedding_backend", "triton"),
        "embedding_model": bank.get("embedding_model", ""),
    }


def _sync_vearch_filter_fields(es: ESClient, bank_id: str, sample_id: str, changes: dict):
    """On sample update, sync affected Vearch columns:
    - String filter fields (custom + sys_ referenced): write new value (truncated to 255 bytes).
    - Vector fields (custom + sys_chunk if enabled): re-embed and update {field}_vector.

    Upsert semantics: if the Vearch doc doesn't exist yet (e.g. it was deposited with an
    empty vector field so was skipped, then an agent later filled in the field), insert
    a full doc using the current ES sample as the source of truth.
    """
    cfg = _get_vearch_field_config(es, bank_id)
    filter_updates: dict = {}
    vector_updates: dict[str, str] = {}

    for k, v in changes.items():
        if k in cfg["filter_fields"]:
            sval = "" if v is None else str(v)
            while len(sval.encode("utf-8")) > 255:
                sval = sval[:-1]
            filter_updates[k] = sval
        if k in cfg["vector_fields"]:
            vector_updates[k] = "" if v is None else str(v)
        if k == "sys_chunk" and cfg["has_sys_chunk"]:
            vector_updates["sys_chunk"] = "" if v is None else str(v)

    if not filter_updates and not vector_updates:
        return

    try:
        from app.storage.vearch_client import vearch_space_name, VearchClient
        from app.config import get_config
        conf = get_config()
        vearch = VearchClient(
            master_url=conf.vearch.master_url,
            router_url=conf.vearch.router_url,
            db_name=conf.vearch.db_name,
        )
        space_name = vearch_space_name(bank_id)

        # Check if the Vearch doc exists. If not, we need to insert instead of update.
        existing = vearch.get_doc(space_name, sample_id)
        if existing is None:
            _insert_vearch_from_es(es, vearch, bank_id, sample_id, cfg, conf)
            return

        # Doc exists: do partial update.
        combined: dict = dict(filter_updates)

        if vector_updates:
            from app.embedder import create_embedder
            embedder = create_embedder(
                cfg["embedding_backend"],
                cfg["embedding_model"],
                conf,
            )
            texts_to_embed: list[str] = []
            field_order: list[str] = []
            for fname, text in vector_updates.items():
                if text.strip() == "":
                    continue
                texts_to_embed.append(text)
                field_order.append(fname)
            if texts_to_embed:
                embs = embedder.encode_batched(texts_to_embed)
                for i, fname in enumerate(field_order):
                    combined[f"{fname}_vector"] = {"feature": [float(x) for x in embs[i]]}

        if combined:
            vearch.update_doc(space_name, sample_id, combined)
    except Exception as exc:
        logger.warning("Failed to sync Vearch fields for sample %s: %s", sample_id, exc)


def _insert_vearch_from_es(es, vearch, bank_id: str, sample_id: str, cfg: dict, conf):
    """Insert a Vearch doc from the current ES sample. Called when a sample update makes
    the sample eligible for vector search (e.g. an agent filled in a previously-empty
    vector field) but no Vearch doc exists yet.

    Only inserts if the sample has at least one non-empty vector field, otherwise Vearch
    would reject the doc (all vector columns are required)."""
    sample = es.get_doc(f"samples_{bank_id}", sample_id)
    if not sample:
        return

    # Collect vector features
    embedder = None
    vector_features: dict[str, list[float]] = {}
    from app.embedder import create_embedder

    def _get_embedder():
        return create_embedder(cfg["embedding_backend"], cfg["embedding_model"], conf)

    if cfg["has_sys_chunk"]:
        text = sample.get("sys_chunk") or ""
        if text.strip():
            embedder = embedder or _get_embedder()
            emb = embedder.encode([str(text)])[0]
            vector_features["sys_chunk_vector"] = [float(x) for x in emb]

    for vf in cfg["vector_fields"]:
        text = sample.get(vf) or ""
        if not text or not str(text).strip():
            continue
        embedder = embedder or _get_embedder()
        emb = embedder.encode([str(text)])[0]
        vector_features[f"{vf}_vector"] = [float(x) for x in emb]

    if not vector_features:
        # No vector data to insert; leave Vearch alone.
        return

    # Get the Vearch space schema to know which filter fields are required
    from app.storage.vearch_client import vearch_space_name
    space_name = vearch_space_name(bank_id)
    space_info = vearch.get_space(space_name) or {}
    space_props = space_info.get("properties", {}) or {}
    required_string_fields = {
        fname for fname, fdef in space_props.items()
        if fdef.get("type") == "string" and fname not in ("sys_sample_id", "sys_document_id")
    }

    entry: dict = {
        "sys_sample_id": sample_id,
        "sys_document_id": sample.get("sys_document_id", ""),
    }
    for fname, feat in vector_features.items():
        entry[fname] = {"feature": feat}
    for ff in required_string_fields:
        val = sample.get(ff, "")
        sval = "" if val is None else str(val)
        while len(sval.encode("utf-8")) > 255:
            sval = sval[:-1]
        entry[ff] = sval

    vearch.insert(space_name, sample_id, entry)




def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_history(
    es: ESClient,
    bank_id: str,
    sample_id: str,
    changed_fields: dict,
    changed_by: str,
    change_source: str,
    full_snapshot: dict,
) -> None:
    """Append a history entry for a sample."""
    # Determine the next version number
    existing = es.search(
        f"sample_history_{bank_id}",
        query={"term": {"sample_id": sample_id}},
        size=0,
    )
    version = existing["total"] + 1

    history_doc = {
        "sample_id": sample_id,
        "version": version,
        "changed_fields": changed_fields,
        "changed_by": changed_by,
        "change_source": change_source,
        "timestamp": _now_iso(),
        "full_snapshot": full_snapshot,
    }
    es.index_doc(f"sample_history_{bank_id}", history_doc, refresh=False)


async def _publish_status_event(
    event_bus: EventBus | None,
    bank_id: str,
    sample_id: str,
    old_status: str | None,
    new_status: str,
    sample_data: dict,
    source: str = "user",
) -> None:
    """Publish a status-change event if the event bus is available."""
    if event_bus is None:
        return
    event = SampleStatusEvent(
        bank_id=bank_id,
        sample_id=sample_id,
        old_status=old_status,
        new_status=new_status,
        sample_data=sample_data,
        source=source,
    )
    await event_bus.publish(event)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_sample(
    es: ESClient,
    bank_id: str,
    doc_id: str,
    data: dict,
    user: str,
    event_bus: EventBus | None = None,
) -> dict:
    """Create a single sample with system fields auto-populated."""
    sample_id = str(uuid.uuid4())
    now = _now_iso()

    sample = dict(data)
    sample.update({
        "sys_sample_id": sample_id,
        "sys_document_id": doc_id,
        "sys_create_time": now,
        "sys_update_time": now,
        "sys_status": DEFAULT_SAMPLE_STATUS,
    })

    es.index_doc(f"samples_{bank_id}", sample, doc_id=sample_id, refresh=True)
    sample["id"] = sample_id

    # Record initial history
    _record_history(
        es, bank_id, sample_id,
        changed_fields=sample,
        changed_by=user,
        change_source="upload",
        full_snapshot=sample,
    )

    # Publish event
    await _publish_status_event(
        event_bus, bank_id, sample_id,
        old_status=None,
        new_status=DEFAULT_SAMPLE_STATUS,
        sample_data=sample,
        source="user",
    )

    return sample


async def create_samples_bulk(
    es: ESClient,
    bank_id: str,
    doc_id: str,
    samples_data: list[dict],
    user: str,
    event_bus: EventBus | None = None,
) -> list[dict]:
    """Bulk-create samples, record initial history entries, publish events."""
    now = _now_iso()
    samples: list[dict] = []

    for data in samples_data:
        sample_id = str(uuid.uuid4())
        sample = dict(data)
        sample.update({
            "sys_sample_id": sample_id,
            "sys_document_id": doc_id,
            "sys_create_time": now,
            "sys_update_time": now,
            "sys_status": DEFAULT_SAMPLE_STATUS,
            "id": sample_id,
        })
        samples.append(sample)

    # Bulk index into ES
    bulk_docs = []
    for s in samples:
        doc = {k: v for k, v in s.items()}  # copy
        bulk_docs.append(doc)
    es.bulk_index(f"samples_{bank_id}", bulk_docs, id_field="id", refresh=True)

    # Record history and publish events for each sample
    for sample in samples:
        sample_id = sample["id"]
        _record_history(
            es, bank_id, sample_id,
            changed_fields=sample,
            changed_by=user,
            change_source="upload",
            full_snapshot=sample,
        )
        await _publish_status_event(
            event_bus, bank_id, sample_id,
            old_status=None,
            new_status=DEFAULT_SAMPLE_STATUS,
            sample_data=sample,
            source="user",
        )

    return samples


def get_sample(es: ESClient, bank_id: str, sample_id: str) -> dict | None:
    """Return a single sample by ID."""
    return es.get_doc(f"samples_{bank_id}", sample_id)


def list_samples(
    es: ESClient,
    bank_id: str,
    query_params: dict | None = None,
) -> dict:
    """Paginated and filtered sample listing.

    Supported query_params:
        - page (int): page number, default 1
        - size (int): page size, default 20
        - doc_id (str): filter by sys_document_id
        - status (str): filter by sys_status
        - executor (str): filter by sys_executor
    """
    params = query_params or {}
    page = int(params.get("page", 1))
    size = int(params.get("size", 20))
    from_ = (max(page, 1) - 1) * size

    filters: list[dict] = []
    if params.get("doc_id"):
        filters.append({"term": {"sys_document_id": params["doc_id"]}})
    if params.get("status"):
        filters.append({"term": {"sys_status": params["status"]}})
    if params.get("executor"):
        filters.append({"term": {"sys_executor": params["executor"]}})

    query: dict[str, Any] | None = None
    if filters:
        query = {"bool": {"filter": filters}}

    result = es.search(
        f"samples_{bank_id}",
        query=query,
        size=size,
        from_=from_,
        sort=[{"sys_create_time": {"order": "desc"}}],
    )
    return {
        "total": result["total"],
        "items": result["items"],
        "page": page,
        "size": size,
    }


async def update_sample(
    es: ESClient,
    bank_id: str,
    sample_id: str,
    changes: dict,
    user: str,
    event_bus: EventBus | None = None,
    source: str = "user",
) -> dict | None:
    """Update a sample, record history, publish event if status changed.
    Also sync filter fields to Vearch if changed.
    """
    existing = es.get_doc(f"samples_{bank_id}", sample_id)
    if existing is None:
        return None

    old_status = existing.get("sys_status")
    changes["sys_update_time"] = _now_iso()

    es.update_doc(f"samples_{bank_id}", sample_id, changes, refresh=True)

    # Sync changed filter fields to Vearch
    _sync_vearch_filter_fields(es, bank_id, sample_id, changes)

    # Build full snapshot after update
    full_snapshot = dict(existing)
    full_snapshot.update(changes)

    # Record history with only the changed fields
    _record_history(
        es, bank_id, sample_id,
        changed_fields=changes,
        changed_by=user,
        change_source=source,
        full_snapshot=full_snapshot,
    )

    # Publish event if status changed
    new_status = changes.get("sys_status")
    if new_status and new_status != old_status:
        await _publish_status_event(
            event_bus, bank_id, sample_id,
            old_status=old_status,
            new_status=new_status,
            sample_data=full_snapshot,
            source=source,
        )

    return full_snapshot


def delete_sample(
    es: ESClient,
    vearch: VearchClient,
    bank_id: str,
    sample_id: str,
) -> bool:
    """Delete a sample from ES and Vearch, update document sample_count."""
    # Get sample to find its document_id
    sample = es.get_doc(f"samples_{bank_id}", sample_id)
    doc_id = sample.get("sys_document_id", "") if sample else ""

    # Delete from Vearch
    space_name = vearch_space_name(bank_id)
    try:
        vearch.delete_doc(space_name, sample_id)
    except Exception as exc:
        logger.error("Vearch delete failed for sample %s: %s", sample_id, exc)

    # Delete history entries
    es.delete_by_query(
        f"sample_history_{bank_id}",
        {"term": {"sample_id": sample_id}},
        refresh=False,
    )

    # Delete the sample itself
    result = es.delete_doc(f"samples_{bank_id}", sample_id, refresh=True)

    # Update document sample_count
    if doc_id:
        try:
            doc = es.get_doc(f"documents_{bank_id}", doc_id)
            if doc:
                new_count = max(0, (doc.get("sample_count", 1)) - 1)
                es.update_doc(f"documents_{bank_id}", doc_id, {"sample_count": new_count}, refresh=True)
        except Exception:
            pass

    return result


def get_sample_history(
    es: ESClient,
    bank_id: str,
    sample_id: str,
) -> list[dict]:
    """Return all history entries for a sample, sorted by version ascending."""
    result = es.search(
        f"sample_history_{bank_id}",
        query={"term": {"sample_id": sample_id}},
        size=10000,
        sort=[{"version": {"order": "asc"}}],
    )
    return result.get("items", [])
