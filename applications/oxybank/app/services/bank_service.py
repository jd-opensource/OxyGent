from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.embedder import create_embedder
from app.storage.es_client import ESClient
from app.storage.vearch_client import VearchClient, vearch_space_name

logger = logging.getLogger("oxybank.bank_service")

# ---------------------------------------------------------------------------
# Scene templates
# ---------------------------------------------------------------------------

SCENE_TEMPLATES: dict[str, dict] = {
    "qa": {
        "id": "qa",
        "name": "QA",
        "description": "qa",
        "has_sys_chunk": False,
        "fields": [
            {"name": "query", "type": "text", "description": "问题"},
            {"name": "answer", "type": "text", "description": "答案"},
            {"name": "is_satisfied", "type": "string", "description": "是否满意"},
            {"name": "reason", "type": "string", "description": "原因"},
        ],
    },
    "memory": {
        "id": "memory",
        "name": "记忆",
        "description": "memory",
        "has_sys_chunk": False,
        "fields": [
            {"name": "query", "type": "text", "description": "问题"},
            {"name": "answer", "type": "text", "description": "答案"},
            {"name": "experience", "type": "string", "description": "经验"},
        ],
    },
    "customer_service": {
        "id": "customer_service",
        "name": "客服FAQ",
        "description": "FAQ-style knowledge bank with question/answer pairs and category tags.",
        "has_sys_chunk": False,
        "fields": [
            {"name": "question", "type": "text", "description": "问题"},
            {"name": "answer", "type": "text", "description": "答案"},
            {"name": "category", "type": "string", "description": "分类"},
        ],
    },
    "knowledge_base": {
        "id": "knowledge_base",
        "name": "知识库",
        "description": "Knowledge articles with title, content, source, and tags.",
        "has_sys_chunk": True,
        "fields": [
            {"name": "title", "type": "text", "description": "标题"},
            {"name": "content", "type": "text", "description": "内容"},
            {"name": "source", "type": "string", "description": "来源"},
            {"name": "tags", "type": "string", "description": "标签"},
        ],
    },
    "product_catalog": {
        "id": "product_catalog",
        "name": "产品目录",
        "description": "Product information with name, description, price, and category.",
        "has_sys_chunk": False,
        "fields": [
            {"name": "product_name", "type": "text", "description": "产品名称"},
            {"name": "description", "type": "text", "description": "描述"},
            {"name": "price", "type": "float", "description": "价格"},
            {"name": "category", "type": "string", "description": "分类"},
        ],
    },
}


def get_scene_templates() -> list[dict]:
    """Return the list of available scene templates."""
    return list(SCENE_TEMPLATES.values())


# ---------------------------------------------------------------------------
# Vearch space helpers
# ---------------------------------------------------------------------------

def _collect_vector_fields(retrieval_apis: list[dict] | None) -> set[str]:
    """Return the set of custom (non-sys_chunk) field names that appear as vector
    conditions in any retrieval API. These need dedicated {field}_vector columns
    in the Vearch space so we can search on them.
    """
    vector_fields: set[str] = set()
    for api_def in (retrieval_apis or []):
        for cond in api_def.get("search_conditions", []):
            mode = cond.get("mode", "exact")
            field = cond.get("field", "")
            if mode == "vector" and field and field != "sys_chunk":
                vector_fields.add(field)
    return vector_fields


def _collect_sys_filter_fields(retrieval_apis: list[dict] | None) -> set[str]:
    """Return the set of sys_ fields (excluding sys_chunk / sys_sample_id / sys_document_id)
    that are referenced as non-vector filter conditions. These sys_ fields also need to be
    stored in Vearch so that native filter can apply on them.
    """
    always_in_vearch = {"sys_sample_id", "sys_document_id"}
    fields: set[str] = set()
    for api_def in (retrieval_apis or []):
        for cond in api_def.get("search_conditions", []):
            mode = cond.get("mode", "exact")
            field = cond.get("field", "")
            if not field or not field.startswith("sys_"):
                continue
            if field in always_in_vearch or field == "sys_chunk":
                continue
            if mode == "vector":
                continue
            fields.add(field)
    return fields


def validate_retrieval_apis(retrieval_apis: list[dict] | None) -> None:
    """Raise ValueError if any sys_ field (other than sys_chunk) is set to vector mode.
    Only sys_chunk is allowed as a vector-search system field; other sys_ fields are
    metadata-only and cannot be embedded meaningfully.
    """
    for api_def in (retrieval_apis or []):
        for cond in api_def.get("search_conditions", []):
            field = cond.get("field", "")
            mode = cond.get("mode", "exact")
            if mode == "vector" and field.startswith("sys_") and field != "sys_chunk":
                raise ValueError(
                    f"System field '{field}' cannot be used for vector search. "
                    f"Only 'sys_chunk' and custom fields support vector mode."
                )


def get_bank_vector_fields(bank: dict) -> list[str]:
    """Public helper: list custom vector-search fields configured on a bank.
    Used by deposit / upload / rebuild paths to know which fields to embed.
    """
    return sorted(_collect_vector_fields(bank.get("retrieval_apis", [])))


def get_bank_sys_filter_fields(bank: dict) -> list[str]:
    """Public helper: list sys_ fields (excluding sys_chunk/sys_sample_id/sys_document_id)
    that must be stored in Vearch for native filtering.
    """
    return sorted(_collect_sys_filter_fields(bank.get("retrieval_apis", [])))


def _build_vearch_properties(
    schema_fields: list[dict],
    has_sys_chunk: bool,
    embedding_backend: str,
    embedding_model: str | None,
    retrieval_apis: list[dict] | None = None,
) -> dict:
    """Build the properties dict for a Vearch space.

    Includes: sys_sample_id, sys_document_id (always indexed),
    sys_chunk_vector if has_sys_chunk, one {field}_vector per custom vector-mode
    field in retrieval APIs, and all non-vector filter fields from retrieval APIs.
    """
    properties: dict[str, Any] = {
        "sys_sample_id": {"type": "string", "index": True},
        "sys_document_id": {"type": "string", "index": True},
    }

    custom_vector_fields = _collect_vector_fields(retrieval_apis)
    need_embedder = has_sys_chunk or bool(custom_vector_fields)
    dim = None
    if need_embedder:
        embedder = create_embedder(embedding_backend, embedding_model)
        dim = embedder.get_dimension()

    if has_sys_chunk:
        properties["sys_chunk_vector"] = {
            "type": "vector",
            "dimension": dim,
            "format": "normalization",
        }

    for vf in custom_vector_fields:
        properties[f"{vf}_vector"] = {
            "type": "vector",
            "dimension": dim,
            "format": "normalization",
        }

    # Collect all non-vector filter fields from non-default retrieval APIs
    filter_fields: set[str] = set()
    for api_def in (retrieval_apis or []):
        if api_def.get("is_default"):
            continue
        for cond in api_def.get("search_conditions", []):
            mode = cond.get("mode", "exact")
            field = cond.get("field", "")
            if field and mode != "vector" and field not in properties and not field.startswith("sys_"):
                filter_fields.add(field)

    # Also add text-type schema fields
    for field in schema_fields:
        name = field.get("name", "")
        if not name or name == "sys_chunk" or name in properties:
            continue
        if name in filter_fields or field.get("type") == "text":
            filter_fields.add(name)

    for fname in filter_fields:
        if fname not in properties:
            properties[fname] = {"type": "string", "index": True}

    # sys_ filter fields referenced by any retrieval API also go into Vearch
    sys_filter_fields = _collect_sys_filter_fields(retrieval_apis)
    for fname in sys_filter_fields:
        if fname not in properties:
            properties[fname] = {"type": "string", "index": True}

    return properties


# ---------------------------------------------------------------------------
# Default retrieval API
# ---------------------------------------------------------------------------

SYSTEM_QUERYABLE_FIELDS = [
    "sys_sample_id", "sys_document_id", "sys_template", "sys_priority",
    "sys_status", "sys_executor", "sys_overview", "sys_remarks",
    "sys_create_time", "sys_update_time",
]


def _build_default_retrieval_api(schema_fields: list[dict], has_sys_chunk: bool) -> dict:
    """Build the default retrieval API: all fields as exact-match conditions, all as output."""
    all_field_names = list(SYSTEM_QUERYABLE_FIELDS)
    if has_sys_chunk:
        all_field_names.append("sys_chunk")
    for f in schema_fields:
        name = f.get("name", "")
        if name and name not in all_field_names:
            all_field_names.append(name)

    conditions = [{"field": f, "mode": "exact"} for f in all_field_names]
    return {
        "id": "default",
        "name": "默认检索接口",
        "is_default": True,
        "search_conditions": conditions,
        "output_fields": all_field_names,
    }


# ---------------------------------------------------------------------------
# Bank CRUD
# ---------------------------------------------------------------------------

def create_bank(
    es: ESClient,
    vearch: VearchClient,
    data: dict,
    user: str,
) -> dict:
    """Create a new bank, its per-bank ES indices, and its Vearch space."""
    name = data.get("name", "").strip()
    if not name:
        raise ValueError("Bank name is required")
    if get_bank_by_name(es, name) is not None:
        raise ValueError(f"Bank name '{name}' already exists")

    bank_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    schema_fields: list[dict] = data.get("schema", [])
    if isinstance(schema_fields, dict):
        schema_fields = schema_fields.get("fields", [])
    has_sys_chunk: bool = data.get("has_sys_chunk", False)
    embedding_backend: str = data.get("embedding_backend", "triton")
    embedding_model: str | None = data.get("embedding_model")

    # Build retrieval APIs — always include a default one
    retrieval_apis = list(data.get("retrieval_apis", []))
    default_api = _build_default_retrieval_api(schema_fields, has_sys_chunk)
    retrieval_apis.insert(0, default_api)

    # Validate: reject non-sys_chunk sys_ fields set to vector mode
    validate_retrieval_apis(retrieval_apis)

    bank_doc = {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "schema_mode": data.get("schema_mode", "custom"),
        "has_sys_chunk": has_sys_chunk,
        "scene_template_id": data.get("scene_template_id", ""),
        "schema": {"fields": schema_fields},
        "embedding_backend": embedding_backend,
        "embedding_model": embedding_model or "",
        "retrieval_apis": retrieval_apis,
        "created_by": user,
        "created_at": now,
        "updated_at": now,
    }

    es.index_doc("banks", bank_doc, doc_id=bank_id, refresh=True)

    # Per-bank Elasticsearch indices
    es.ensure_bank_indices(bank_id, schema_fields, has_sys_chunk)

    # Vearch vector space — only create if there is at least one vector field
    vearch_props = _build_vearch_properties(
        schema_fields, has_sys_chunk, embedding_backend, embedding_model, retrieval_apis,
    )
    has_any_vector = any(p.get("type") == "vector" for p in vearch_props.values())
    space_name = vearch_space_name(bank_id)
    if has_any_vector:
        try:
            vearch.create_space(space_name, vearch_props)
            logger.info("Created Vearch space %s", space_name)
        except Exception as exc:
            logger.error("Failed to create Vearch space %s: %s", space_name, exc)
    else:
        logger.info("Skipping Vearch space for bank %s (no vector fields)", bank_id)

    bank_doc["id"] = bank_id

    # Create built-in annotation templates for known scenes
    scene_id = data.get("scene_template_id", "")
    default_tpl_id = _create_builtin_templates(es, bank_id, scene_id, user, now)
    if default_tpl_id:
        bank_doc["default_template_id"] = default_tpl_id
        es.update_doc("banks", bank_id, {"default_template_id": default_tpl_id}, refresh=True)

    return bank_doc


# ---------------------------------------------------------------------------
# Built-in annotation templates per scene
# ---------------------------------------------------------------------------

BUILTIN_TEMPLATES: dict[str, list[dict]] = {
    "qa": [
        {
            "name": "builtin_qa",
            "description": "Label whether the answer is satisfactory, and why not if it isn't",
            "editable_fields": ["is_satisfied", "reason"],
            "field_constraints": {
                "is_satisfied": {
                    "type": "radio",
                    "options": ["Satisfied", "Unsatisfied"],
                    "required": True,
                },
                "reason": {
                    "type": "textarea",
                    "placeholder": "Why is the answer unsatisfactory?",
                    "show_when": {"is_satisfied": "Unsatisfied"},
                },
            },
            "layout": {
                "sections": [
                    {"title": "QA Content", "fields": ["query", "answer"], "readonly": True},
                    {"title": "Annotation", "fields": ["is_satisfied", "reason"]},
                ],
            },
        },
    ],
    "knowledge_base": [
        {
            "name": "builtin_business",
            "description": "Label the business domain the document belongs to",
            "editable_fields": ["business"],
            "field_constraints": {
                "business": {
                    "type": "radio",
                    "options": [
                        "Home Appliances", "Consumer Electronics", "Apparel", "Food & Beverage",
                        "Home & Building", "Maternity & Baby", "Beauty & Personal Care",
                        "Health & Medical", "Sports & Outdoors", "Auto Accessories",
                    ],
                    "required": True,
                },
            },
            "layout": {
                "sections": [
                    {"title": "Document Content", "fields": ["sys_chunk"], "readonly": True},
                    {"title": "Business Domain", "fields": ["business"]},
                ],
            },
        },
    ],
}


def init_builtin_templates(es: ESClient):
    """Ensure all built-in templates exist in ES. Always overwrite to pick up code changes.

    Also purges built-in template docs that no longer exist in the code registry — this
    keeps the DB in sync with BUILTIN_TEMPLATES and avoids orphaned 'built-in' entries
    (e.g. from removed scene definitions) surviving indefinitely.

    The doc shape here MUST match what create_template writes for user templates so that
    render/edit/save code paths don't have to special-case them. Fields kept: bank_id,
    name, description, editable_fields, field_constraints, layout, is_builtin, created_by,
    created_at, updated_at. Note: sample status transitions are driven by sample-level
    sys_next_status / sys_prev_status, not by any template field.

    Doc identity: the template's `name` doubles as its ES doc_id (see BUILTIN_TEMPLATES —
    each entry has only `name`, no separate `id`). This mirrors AI-generated templates
    which also don't carry a separate id field.
    """
    now = datetime.now(timezone.utc).isoformat()
    known_ids: set[str] = set()
    for scene_id, templates in BUILTIN_TEMPLATES.items():
        for tpl in templates:
            name = tpl.get("name")
            if not name:
                continue
            known_ids.add(name)
            doc = {
                "bank_id": "_builtin",
                "name": name,
                "description": tpl.get("description", ""),
                "editable_fields": tpl.get("editable_fields", []),
                "field_constraints": tpl.get("field_constraints", {}),
                "layout": tpl.get("layout", {}),
                "is_builtin": True,
                "created_by": "system",
                "created_at": now,
                "updated_at": now,
            }
            es.index_doc("templates", doc, doc_id=name, refresh=True)
            logger.info("Created built-in template '%s'", name)

    # Purge orphaned built-ins that used to exist in the code registry but no longer do.
    try:
        existing = es.search(
            "templates",
            query={"term": {"bank_id": "_builtin"}},
            size=1000,
        )
        for doc in existing.get("items", []):
            did = doc.get("id")
            if did and did not in known_ids:
                es.delete_doc("templates", did, refresh=True)
                logger.info("Removed orphaned built-in template '%s' (id=%s)", doc.get("name"), did)
    except Exception as exc:
        logger.warning("Failed to purge orphaned built-in templates: %s", exc)


def _create_builtin_templates(es: ESClient, bank_id: str, scene_id: str, user: str, now: str) -> str | None:
    """Return the default template ID (= its name) for the given scene, or None if the
    scene has no built-in templates.

    Historically this function also created per-bank copies of built-in templates.
    Templates are now global (see template_service._GLOBAL_BANK_ID) — init_builtin_templates()
    creates them once at startup, so nothing to duplicate here. Kept as a thin lookup
    helper so create_bank can still stamp `bank.default_template_id`.
    """
    templates = BUILTIN_TEMPLATES.get(scene_id, [])
    if not templates:
        return None
    return templates[0].get("name")


def list_banks(es: ESClient) -> dict:
    """Return all banks."""
    result = es.search("banks", size=10000)
    return result


def get_bank(es: ESClient, bank_id: str) -> dict | None:
    """Return a single bank by ID, or None if not found."""
    return es.get_doc("banks", bank_id)


def get_bank_by_name(es: ESClient, name: str) -> dict | None:
    """Return a single bank by name, or None if not found."""
    result = es.search("banks", query={"term": {"name.keyword": name}}, size=1)
    items = result.get("items", [])
    if not items:
        result = es.search("banks", query={"term": {"name": name}}, size=1)
        items = result.get("items", [])
    return items[0] if items else None


def resolve_bank(es: ESClient, bank_name: str) -> dict | None:
    """Resolve bank by name. Returns bank dict or None."""
    return get_bank_by_name(es, bank_name)


def update_bank(es: ESClient, bank_id: str, data: dict) -> dict | None:
    """Partial update of a bank document."""
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    es.update_doc("banks", bank_id, data, refresh=True)
    return es.get_doc("banks", bank_id)


def delete_bank(
    es: ESClient,
    vearch: VearchClient,
    bank_id: str,
) -> bool:
    """Delete a bank and all of its per-bank ES indices + Vearch space."""
    # Delete per-bank ES indices
    es.delete_bank_indices(bank_id)

    # Delete Vearch space
    space_name = vearch_space_name(bank_id)
    try:
        vearch.delete_space(space_name)
    except Exception as exc:
        logger.error("Failed to delete Vearch space %s: %s", space_name, exc)

    # Delete the bank document itself
    return es.delete_doc("banks", bank_id, refresh=True)
