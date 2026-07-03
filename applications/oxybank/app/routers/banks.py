from __future__ import annotations

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, require_admin, resolve_bank_id
from app.services import bank_service
from app.services.sample_service import DEFAULT_SAMPLE_STATUS
from app.storage.vearch_client import vearch_space_name

logger = logging.getLogger("oxybank.banks")
from app.models.bank import BankCreate, BankUpdate, SchemaField

router = APIRouter()


# ---------------------------------------------------------------------------
# POST / - create bank
# ---------------------------------------------------------------------------
@router.post("")
async def create_bank(
    data: BankCreate,
    request: Request,
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    vearch = request.app.state.vearch
    try:
        from app.services import bank_service

        payload = data.model_dump()
        payload["schema"] = payload.pop("schema_fields", [])
        retrieval_apis = payload.get("retrieval_apis", [])
        for api_def in retrieval_apis:
            if not api_def.get("id"):
                import re
                name = api_def.get("name", "api")
                api_def["id"] = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
        result = bank_service.create_bank(es, vearch, payload, user.get("username", ""))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET / - list all banks
# ---------------------------------------------------------------------------
@router.get("")
async def list_banks(
    request: Request,
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import bank_service

        result = bank_service.list_banks(es)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ---------------------------------------------------------------------------
# GET /scene-templates - list scene templates
# ---------------------------------------------------------------------------
@router.get("/scene-templates")
async def list_scene_templates(
    user: dict = Depends(get_current_user),
):
    try:
        from app.services import bank_service

        result = bank_service.get_scene_templates()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{bank_id} - get bank detail
# ---------------------------------------------------------------------------
@router.get("/{bank_name}")
async def get_bank(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import bank_service

        result = bank_service.get_bank(es, bank_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Bank not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{bank_id}/tools - list all tools (retrieve + deposit) for a bank
# ---------------------------------------------------------------------------
@router.get("/{bank_name}/list_banks")
async def list_bank_tools(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import bank_service

        bank = bank_service.get_bank(es, bank_id)
        if bank is None:
            raise HTTPException(status_code=404, detail="Bank not found")

        schema_fields = bank.get("schema", {})
        if isinstance(schema_fields, dict):
            schema_fields = schema_fields.get("fields", [])
        has_sys_chunk = bank.get("has_sys_chunk", False)

        tools = []

        # --- Deposit tool ---
        deposit_props = {}
        for f in schema_fields:
            fname = f.get("name", "")
            ftype = f.get("type", "string")
            fdesc = f.get("description", fname)
            if fname:
                deposit_props[fname] = {"description": fdesc, "type": ftype}
        if has_sys_chunk:
            deposit_props["sys_chunk"] = {"description": "Document chunk content", "type": "text"}
        deposit_props["sys_status"] = {"description": "Sample status", "type": "string"}
        deposit_props["sys_priority"] = {"description": "Annotation priority", "type": "integer"}

        tools.append({
            "name": "deposit",
            "endpoint": "/deposit",
            "method": "POST",
            "type": "deposit",
            "description": f"Deposit a single sample into bank '{bank.get('name', '')}'",
            "inputSchema": {
                "type": "object",
                "properties": deposit_props,
                "required": [],
            },
        })

        tools.append({
            "name": "deposit_batch",
            "endpoint": "/deposit_batch",
            "method": "POST",
            "type": "deposit",
            "description": f"Batch deposit samples into bank '{bank.get('name', '')}'",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "samples": {
                        "description": "Array of sample objects",
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": deposit_props,
                        },
                    },
                    "document_name": {"description": "Batch name for traceability", "type": "string"},
                },
                "required": ["samples"],
            },
        })

        # --- Retrieval tools ---
        retrieval_apis = bank.get("retrieval_apis", [])
        for api_def in retrieval_apis:
            api_id = api_def.get("id", "")
            api_name = api_def.get("name", api_id)
            is_default = api_def.get("is_default", False)
            conditions = api_def.get("search_conditions", [])
            output_fields = api_def.get("output_fields", [])

            cond_props = {}
            for c in conditions:
                field = c.get("field", "")
                mode = c.get("mode", "exact")
                mode_desc = {"exact": "Exact match (==)", "in": "IN match (array)", "fuzzy": "Fuzzy text match", "vector": "Vector similarity search"}.get(mode, mode)
                if field:
                    cond_props[field] = {"description": f"{field} ({mode_desc})", "type": "string"}

            cond_props["page_size"] = {"description": "Items per page (default 10)", "type": "integer"}
            cond_props["page_number"] = {"description": "Page number, starts from 1", "type": "integer"}

            tool_name = "withdraw" if is_default else f"{api_name.replace(' ', '_').lower()}_withdraw"
            endpoint = "/withdraw" if is_default else f"/{api_id}/withdraw"
            tools.append({
                "name": tool_name,
                "endpoint": endpoint,
                "method": "POST",
                "type": "retrieve",
                "description": f"{'Default retrieval' if is_default else api_name} for bank '{bank.get('name', '')}'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "conditions": {
                            "description": "Search conditions (field -> value)",
                            "type": "object",
                            "properties": cond_props,
                        },
                        "page_size": {"description": "Items per page (default 10)", "type": "integer"},
                        "page_number": {"description": "Page number (default 1)", "type": "integer"},
                    },
                    "required": [],
                },
                "outputFields": output_fields,
            })

        return tools
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /{bank_name}/withdraw - default retrieval
# POST /{bank_name}/{api_id}/withdraw - custom retrieval
# ---------------------------------------------------------------------------
async def _execute_bank_query(bank_id: str, api_id: str | None, request: Request):
    es = request.app.state.es
    vearch = request.app.state.vearch
    from app.services import retrieval_service

    bank = bank_service.get_bank(es, bank_id)
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found")

    retrieval_apis = bank.get("retrieval_apis", [])
    api_def = None
    if api_id:
        for a in retrieval_apis:
            if a.get("id") == api_id:
                api_def = a
                break
    else:
        for a in retrieval_apis:
            if a.get("is_default"):
                api_def = a
                break
    if api_def is None:
        raise HTTPException(status_code=404, detail="Retrieval API not found")

    body = await request.json()
    from app.embedder import create_embedder
    from app.config import get_config
    config = get_config()
    embedder = create_embedder(
        bank.get("embedding_backend", "triton"),
        bank.get("embedding_model", ""),
        config,
    )
    return retrieval_service.execute_retrieval(
        es=es, vearch=vearch, embedder=embedder,
        bank_id=bank_id, api_def=api_def, query_data=body,
    )


@router.post("/{bank_name}/withdraw")
async def default_query(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    try:
        return await _execute_bank_query(bank_id, None, request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{bank_name}/{api_id}/withdraw")
async def custom_query(
    api_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    try:
        return await _execute_bank_query(bank_id, api_id, request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
@router.put("/{bank_name}")
async def update_bank(
    data: BankUpdate,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    try:
        from app.services import bank_service

        result = bank_service.update_bank(es, bank_id, data.model_dump(exclude_none=True))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /{bank_name}/rebuild-vearch - recreate Vearch space and backfill vectors
# ---------------------------------------------------------------------------
@router.post("/{bank_name}/rebuild-vearch")
async def rebuild_vearch(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    """Recreate the Vearch space for a bank based on the current retrieval-API
    definitions, and backfill all samples' vector fields from ES."""
    es = request.app.state.es
    vearch = request.app.state.vearch
    try:
        from app.services import bank_service
        from app.services.bank_service import (
            _build_vearch_properties,
            get_bank_vector_fields,
        )
        from app.embedder import create_embedder as _create_embedder
        from app.config import get_config as _get_config

        bank = bank_service.get_bank(es, bank_id)
        if bank is None:
            raise HTTPException(status_code=404, detail="Bank not found")

        has_sys_chunk = bank.get("has_sys_chunk", False)
        custom_vector_fields = get_bank_vector_fields(bank)
        if not has_sys_chunk and not custom_vector_fields:
            return {"message": "No vector fields configured; nothing to rebuild.", "samples_indexed": 0}

        # Recreate the space
        schema_fields = bank.get("schema", {}).get("fields", [])
        vearch_props = _build_vearch_properties(
            schema_fields,
            has_sys_chunk,
            bank.get("embedding_backend", "triton"),
            bank.get("embedding_model", ""),
            bank.get("retrieval_apis", []),
        )
        space_name = vearch_space_name(bank_id)
        vearch.delete_space(space_name)
        vearch.create_space(space_name, vearch_props)
        # Give Vearch a moment to make the new space available for writes.
        import time
        time.sleep(1.5)

        # Fetch all samples from ES (paginate)
        cfg = _get_config()
        embedder = _create_embedder(
            bank.get("embedding_backend", "triton"),
            bank.get("embedding_model", ""),
            cfg,
        )
        # Any non-vector string property in the space needs a value on every doc,
        # because Vearch rejects docs whose field count doesn't match the space schema.
        # sys_sample_id / sys_document_id are handled explicitly below, so exclude them here.
        vearch_filter_fields = {
            fname for fname, fdef in vearch_props.items()
            if fdef.get("type") == "string" and fname not in ("sys_sample_id", "sys_document_id")
        }

        page_size = 500
        from_ = 0
        total_indexed = 0
        while True:
            result = es.search(
                f"samples_{bank_id}",
                query=None,
                size=page_size,
                from_=from_,
            )
            items = result.get("items", [])
            if not items:
                break

            # Embed sys_chunk texts for this batch
            sys_chunk_vecs: dict[int, list[float]] = {}
            if has_sys_chunk:
                idxs = [i for i, s in enumerate(items) if s.get("sys_chunk")]
                texts = [items[i]["sys_chunk"] for i in idxs]
                if texts:
                    embs = embedder.encode_batched(texts)
                    for i, emb in zip(idxs, embs):
                        sys_chunk_vecs[i] = [float(x) for x in emb]

            custom_vecs: dict[str, dict[int, list[float]]] = {}
            for vf in custom_vector_fields:
                idxs = []
                texts = []
                for i, s in enumerate(items):
                    val = s.get(vf)
                    if val is not None and str(val).strip() != "":
                        idxs.append(i)
                        texts.append(str(val))
                if not texts:
                    continue
                embs = embedder.encode_batched(texts)
                custom_vecs[vf] = {i: [float(x) for x in emb] for i, emb in zip(idxs, embs)}

            vearch_docs = []
            for i, s in enumerate(items):
                has_any = i in sys_chunk_vecs or any(
                    i in custom_vecs.get(vf, {}) for vf in custom_vector_fields
                )
                if not has_any:
                    continue
                sample_id = s.get("sys_sample_id") or s.get("id", "")
                entry: dict = {
                    "sys_sample_id": sample_id,
                    "sys_document_id": s.get("sys_document_id", ""),
                }
                if i in sys_chunk_vecs:
                    entry["sys_chunk_vector"] = {"feature": sys_chunk_vecs[i]}
                for vf in custom_vector_fields:
                    if i in custom_vecs.get(vf, {}):
                        entry[f"{vf}_vector"] = {"feature": custom_vecs[vf][i]}
                for ff in vearch_filter_fields:
                    # Vearch requires ALL space properties on every doc, so include even missing ones.
                    # Vearch indexed strings are capped at 255 bytes; truncate longer content.
                    val = s.get(ff, "")
                    sval = "" if val is None else str(val)
                    if len(sval.encode("utf-8")) > 255:
                        while len(sval.encode("utf-8")) > 255:
                            sval = sval[:-1]
                    entry[ff] = sval
                vearch_docs.append((sample_id, entry))

            if vearch_docs:
                bulk_result = vearch.bulk_insert(space_name, vearch_docs, refresh=True)
                # Vearch returns a list of per-doc results. Count only those with status:200.
                success_count = 0
                if isinstance(bulk_result, list):
                    for r in bulk_result:
                        if isinstance(r, dict) and r.get("status") == 200:
                            success_count += 1
                else:
                    # Bulk failed at the request level (e.g. 400). Try one-by-one as fallback.
                    logger.warning("Vearch bulk_insert returned non-list result: %s. Falling back to per-doc insert.", bulk_result)
                    for did, doc in vearch_docs:
                        r = vearch.insert(space_name, did, doc)
                        if isinstance(r, dict) and r.get("status") == 200:
                            success_count += 1
                total_indexed += success_count

            if len(items) < page_size:
                break
            from_ += page_size

        return {
            "message": "Vearch index rebuilt successfully",
            "samples_indexed": total_indexed,
            "vector_fields": (["sys_chunk"] if has_sys_chunk else []) + custom_vector_fields,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Rebuild vearch failed for bank %s", bank_id)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# DELETE /{bank_id} - delete bank
# ---------------------------------------------------------------------------
@router.delete("/{bank_name}")
async def delete_bank(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    vearch = request.app.state.vearch
    try:
        from app.services import bank_service

        bank_service.delete_bank(es, vearch, bank_id)
        return {"message": "Bank deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /parse-schema-file - upload CSV/XLSX, parse headers
# ---------------------------------------------------------------------------
@router.post("/parse-schema-file")
async def parse_schema_file(
    file: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("csv", "xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only CSV and XLSX files are accepted.",
        )

    try:
        content = await file.read()

        headers: list[str] = []

        if ext == "csv":
            text = content.decode("utf-8-sig")
            reader = csv.reader(io.StringIO(text))
            first_row = next(reader, None)
            if first_row:
                headers = [h.strip() for h in first_row if h.strip()]

        elif ext == "xlsx":
            import openpyxl

            wb = openpyxl.load_workbook(
                filename=io.BytesIO(content), read_only=True, data_only=True
            )
            ws = wb.active
            if ws is not None:
                first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
                if first_row:
                    headers = [str(cell).strip() for cell in first_row if cell is not None and str(cell).strip()]
            wb.close()

        fields = [
            SchemaField(name=h, type="string", description="")
            for h in headers
        ]
        return fields

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")


# ---------------------------------------------------------------------------
# POST /{bank_id}/deposit - deposit single sample via API
# POST /{bank_id}/deposit_batch - deposit multiple samples via API
# ---------------------------------------------------------------------------

class DepositBatchRequest(BaseModel):
    samples: list[dict]
    document_name: str = ""


@router.post("/{bank_name}/deposit")
async def deposit_single(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    body = await request.json()
    if not body or not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    doc_name = body.pop("document_name", "")
    result = await _deposit_samples(bank_id, [body], doc_name, request, user)
    return {
        "sample_id": result["sample_ids"][0] if result["sample_ids"] else None,
        "document_id": result["document_id"],
    }


@router.post("/{bank_name}/deposit_batch")
async def deposit_batch(
    data: DepositBatchRequest,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    if not data.samples:
        raise HTTPException(status_code=400, detail="samples list is empty")
    return await _deposit_samples(bank_id, data.samples, data.document_name, request, user)


async def _deposit_samples(
    bank_id: str,
    samples: list[dict],
    document_name: str,
    request: Request,
    user: dict,
) -> dict:

    es = request.app.state.es
    vearch = request.app.state.vearch

    from app.services import bank_service

    bank = bank_service.get_bank(es, bank_id)
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found")

    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    now = _dt.now(_tz.utc).isoformat()
    has_sys_chunk = bank.get("has_sys_chunk", False)
    default_tpl_id = bank.get("default_template_id", "")

    # Determine document ID: use provided sys_document_id or generate one
    provided_doc_id = None
    for row in samples:
        if row.get("sys_document_id"):
            provided_doc_id = row["sys_document_id"]
            break
    doc_id = provided_doc_id or str(_uuid.uuid4())
    doc_name = document_name or f"deposit_{now}"

    # Create or update document record
    existing_doc = es.get_doc(f"documents_{bank_id}", doc_id)
    if existing_doc:
        # Append to existing document — update sample count
        old_count = existing_doc.get("sample_count", 0)
        es.update_doc(f"documents_{bank_id}", doc_id, {
            "sample_count": old_count + len(samples),
        }, refresh=True)
    else:
        es.index_doc(f"documents_{bank_id}", {
            "bank_id": bank_id,
            "filename": doc_name,
            "file_type": "deposit",
            "upload_time": now,
            "uploaded_by": user.get("username", ""),
            "sample_count": len(samples),
            "status": "completed",
        }, doc_id=doc_id, refresh=True)

    # Build sample docs
    sample_docs = []
    chunk_texts = []
    sample_ids = []
    for row in samples:
        sample_id = str(_uuid.uuid4())
        sample_ids.append(sample_id)
        sample_doc = {
            "id": sample_id,
            "sys_sample_id": sample_id,
            "sys_document_id": doc_id,
            "sys_template": row.get("sys_template", default_tpl_id),
            "sys_priority": row.get("sys_priority", 0),
            "sys_status": row.get("sys_status", DEFAULT_SAMPLE_STATUS),
            "sys_executor": row.get("sys_executor", ""),
            "sys_overview": row.get("sys_overview", ""),
            "sys_remarks": row.get("sys_remarks", ""),
            "sys_prev_status": "",
            "sys_prev_template": "",
            "sys_prev_executor": "",
            "sys_next_status": row.get("sys_next_status", ""),
            "sys_next_template": row.get("sys_next_template", ""),
            "sys_next_executor": row.get("sys_next_executor", ""),
            "sys_create_time": now,
            "sys_update_time": now,
        }
        # Copy user-provided fields (skip system fields already set)
        for k, v in row.items():
            if not k.startswith("sys_") and k != "id":
                sample_doc[k] = v
        # sys_chunk from user data
        if "sys_chunk" in row:
            sample_doc["sys_chunk"] = row["sys_chunk"]
            chunk_texts.append(row["sys_chunk"])
        else:
            chunk_texts.append(None)

        sample_docs.append(sample_doc)

    # Bulk index into ES
    es.bulk_index(f"samples_{bank_id}", sample_docs, id_field="id", refresh=True)

    # Embed and insert into Vearch — needed if has_sys_chunk OR any custom vector field
    from app.services.bank_service import get_bank_vector_fields
    custom_vector_fields = get_bank_vector_fields(bank)
    if has_sys_chunk or custom_vector_fields:
        try:
            from app.embedder import create_embedder as _create_embedder
            from app.config import get_config as _get_config
            cfg = _get_config()
            embedder = _create_embedder(
                bank.get("embedding_backend", "triton"),
                bank.get("embedding_model", ""),
                cfg,
            )
            # Vearch requires every space property on each doc — use the space schema itself
            # to know which string filter fields need to be populated.
            try:
                space_info = vearch.get_space(vearch_space_name(bank_id)) or {}
                space_props = space_info.get("properties", {})
                vearch_filter_fields = {
                    fname for fname, fdef in space_props.items()
                    if fdef.get("type") == "string" and fname not in ("sys_sample_id", "sys_document_id")
                }
            except Exception:
                vearch_filter_fields = set()
                for api_def in bank.get("retrieval_apis", []):
                    if api_def.get("is_default"):
                        continue
                    for cond in api_def.get("search_conditions", []):
                        field = cond.get("field", "")
                        if field and cond.get("mode", "") != "vector":
                            vearch_filter_fields.add(field)
                # drop the two always-explicit fields
                vearch_filter_fields.discard("sys_sample_id")
                vearch_filter_fields.discard("sys_document_id")

            # Embed sys_chunk texts if enabled
            sys_chunk_vectors: dict[int, list[float]] = {}
            if has_sys_chunk:
                indices_with_chunk = [i for i, t in enumerate(chunk_texts) if t]
                texts = [chunk_texts[i] for i in indices_with_chunk]
                if texts:
                    embs = embedder.encode_batched(texts)
                    for idx, emb in zip(indices_with_chunk, embs):
                        sys_chunk_vectors[idx] = [float(x) for x in emb]

            # Embed each custom vector field
            custom_vectors: dict[str, dict[int, list[float]]] = {}
            for vf in custom_vector_fields:
                indices_with_val: list[int] = []
                texts: list[str] = []
                for i, sdoc in enumerate(sample_docs):
                    val = sdoc.get(vf)
                    if val is not None and str(val).strip() != "":
                        indices_with_val.append(i)
                        texts.append(str(val))
                if not texts:
                    continue
                embs = embedder.encode_batched(texts)
                custom_vectors[vf] = {
                    idx: [float(x) for x in emb]
                    for idx, emb in zip(indices_with_val, embs)
                }

            # Build Vearch docs — one per sample that has at least one vector value
            vearch_docs = []
            for i, sample_id in enumerate(sample_ids):
                has_any_vec = i in sys_chunk_vectors or any(
                    i in custom_vectors.get(vf, {}) for vf in custom_vector_fields
                )
                if not has_any_vec:
                    continue
                vearch_entry: dict = {
                    "sys_sample_id": sample_id,
                    "sys_document_id": doc_id,
                }
                if i in sys_chunk_vectors:
                    vearch_entry["sys_chunk_vector"] = {"feature": sys_chunk_vectors[i]}
                for vf in custom_vector_fields:
                    if i in custom_vectors.get(vf, {}):
                        vearch_entry[f"{vf}_vector"] = {"feature": custom_vectors[vf][i]}
                for ff in vearch_filter_fields:
                    val = sample_docs[i].get(ff, "")
                    sval = "" if val is None else str(val)
                    if len(sval.encode("utf-8")) > 255:
                        while len(sval.encode("utf-8")) > 255:
                            sval = sval[:-1]
                    vearch_entry[ff] = sval
                vearch_docs.append((sample_id, vearch_entry))

            if vearch_docs:
                space_name = vearch_space_name(bank_id)
                vearch.bulk_insert(space_name, vearch_docs, refresh=True)
        except Exception as exc:
            logger.warning("Vearch insert failed during deposit: %s", exc)

    # Publish events for annotation agents
    event_bus = request.app.state.event_bus
    from app.services.event_bus import SampleStatusEvent
    for i, sample_doc in enumerate(sample_docs):
        await event_bus.publish(SampleStatusEvent(
            bank_id=bank_id,
            sample_id=sample_ids[i],
            old_status=None,
            new_status=sample_doc.get("sys_status", DEFAULT_SAMPLE_STATUS),
            sample_data=sample_doc,
        ))

    return {
        "document_id": doc_id,
        "sample_count": len(sample_docs),
        "sample_ids": sample_ids,
    }
