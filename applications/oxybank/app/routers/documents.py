from __future__ import annotations

import csv
import io
import os
import tempfile
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query

from app.auth.dependencies import get_current_user, require_admin, resolve_bank_id
from app.embedder import create_embedder
from app.config import get_config
from app.services import chunking_service, document_service
from app.services.sample_service import DEFAULT_SAMPLE_STATUS
from app.storage.vearch_client import vearch_space_name

router = APIRouter()

# Supported file types
TEXT_FILE_TYPES = {"docx", "pdf", "txt", "md"}
SPREADSHEET_FILE_TYPES = {"xlsx", "csv"}
ALL_SUPPORTED_TYPES = TEXT_FILE_TYPES | SPREADSHEET_FILE_TYPES


def _make_sys_fields(sample_id: str, doc_id: str, default_template_id: str = "") -> dict:
    """Return a complete set of system fields with defaults."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "sys_sample_id": sample_id,
        "sys_document_id": doc_id,
        "sys_template": default_template_id,
        "sys_priority": 0,
        "sys_status": DEFAULT_SAMPLE_STATUS,
        "sys_executor": "",
        "sys_overview": "",
        "sys_remarks": "",
        "sys_prev_status": "",
        "sys_prev_template": "",
        "sys_prev_executor": "",
        "sys_next_status": "",
        "sys_next_template": "",
        "sys_next_executor": "",
        "sys_create_time": now,
        "sys_update_time": now,
    }


def _get_file_extension(filename: str) -> str:
    """Extract lowercase file extension from filename."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _determine_file_type(ext: str) -> str:
    """Map extension to a file type category."""
    mapping = {
        "docx": "word",
        "pdf": "pdf",
        "txt": "text",
        "md": "markdown",
        "xlsx": "excel",
        "csv": "csv",
    }
    return mapping.get(ext, ext)


# ---------------------------------------------------------------------------
# POST /upload - upload file (multipart)
# ---------------------------------------------------------------------------

async def _publish_sample_events(request, bank_id, sample_docs, sample_ids=None):
    """Publish status-change events for newly created samples."""
    from app.services.event_bus import SampleStatusEvent
    event_bus = request.app.state.event_bus
    for i, doc in enumerate(sample_docs):
        sid = sample_ids[i] if sample_ids else doc.get("sys_sample_id", doc.get("id", ""))
        await event_bus.publish(SampleStatusEvent(
            bank_id=bank_id,
            sample_id=sid,
            old_status=None,
            new_status=doc.get("sys_status", DEFAULT_SAMPLE_STATUS),
            sample_data=doc,
        ))


async def _write_custom_vector_fields(bank, sample_docs, doc_id, vearch, bank_id):
    """Embed each custom vector-search field and insert vectors into Vearch.
    Used by spreadsheet / no-sys_chunk upload paths where the main flow doesn't
    already handle Vearch."""
    from app.services.bank_service import get_bank_vector_fields
    custom_vector_fields = get_bank_vector_fields(bank)
    if not custom_vector_fields:
        return
    try:
        config = get_config()
        embedder = create_embedder(
            bank.get("embedding_backend", "triton"),
            bank.get("embedding_model", ""),
            config,
        )
        # Vearch requires every space property on each doc — use the actual space schema.
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
                    f = cond.get("field", "")
                    if f and cond.get("mode", "") != "vector":
                        vearch_filter_fields.add(f)
            vearch_filter_fields.discard("sys_sample_id")
            vearch_filter_fields.discard("sys_document_id")

        custom_vectors: dict[str, dict[int, list[float]]] = {}
        for vf in custom_vector_fields:
            indices: list[int] = []
            texts: list[str] = []
            for i, sdoc in enumerate(sample_docs):
                val = sdoc.get(vf)
                if val is not None and str(val).strip() != "":
                    indices.append(i)
                    texts.append(str(val))
            if not texts:
                continue
            embs = embedder.encode_batched(texts)
            custom_vectors[vf] = {
                idx: [float(x) for x in emb] for idx, emb in zip(indices, embs)
            }

        vearch_docs = []
        for i, sdoc in enumerate(sample_docs):
            has_any = any(i in custom_vectors.get(vf, {}) for vf in custom_vector_fields)
            if not has_any:
                continue
            sample_id = sdoc.get("sys_sample_id") or sdoc.get("id", "")
            entry: dict = {
                "sys_sample_id": sample_id,
                "sys_document_id": doc_id,
            }
            for vf in custom_vector_fields:
                if i in custom_vectors.get(vf, {}):
                    entry[f"{vf}_vector"] = {"feature": custom_vectors[vf][i]}
            for ff in vearch_filter_fields:
                val = sdoc.get(ff, "")
                sval = "" if val is None else str(val)
                if len(sval.encode("utf-8")) > 255:
                    while len(sval.encode("utf-8")) > 255:
                        sval = sval[:-1]
                entry[ff] = sval
            vearch_docs.append((sample_id, entry))

        if vearch_docs:
            space_name = vearch_space_name(bank_id)
            vearch.bulk_insert(space_name, vearch_docs, refresh=True)
    except Exception as exc:
        import logging
        logging.getLogger("oxybank.documents").warning(
            "Custom vector embedding failed for bank %s: %s", bank_id, exc
        )

@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    vearch = request.app.state.vearch

    filename = file.filename or "unnamed"
    ext = _get_file_extension(filename)

    if ext not in ALL_SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Supported: {', '.join(sorted(ALL_SUPPORTED_TYPES))}",
        )

    # Fetch bank info to determine processing strategy
    from app.services import bank_service

    bank = bank_service.get_bank(es, bank_id)
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found")

    default_tpl_id = bank.get("default_template_id", "")
    # Build default values for custom schema fields
    schema_fields_def = bank.get("schema", {})
    if isinstance(schema_fields_def, dict):
        schema_fields_def = schema_fields_def.get("fields", [])
    custom_field_defaults = {}
    for f in schema_fields_def:
        fname = f.get("name", "")
        if fname and not fname.startswith("sys_"):
            custom_field_defaults[fname] = ""
    file_type = _determine_file_type(ext)
    content = await file.read()

    try:
        # -------------------------------------------------------------------
        # Case 1: Text files with sys_chunk enabled
        # -------------------------------------------------------------------
        if bank.get("has_sys_chunk") and ext in TEXT_FILE_TYPES:
            from app.services import sample_service

            # Save to temp file for chunking
            suffix = f".{ext}"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Chunk the file
                chunks = chunking_service.chunk_file(tmp_path)
            finally:
                os.unlink(tmp_path)

            # Create document record
            doc_id = str(uuid.uuid4())
            doc_record = {
                "id": doc_id,
                "bank_id": bank_id,
                "filename": filename,
                "file_type": file_type,
                "upload_time": datetime.now(timezone.utc).isoformat(),
                "uploaded_by": user["username"],
                "sample_count": len(chunks),
                "status": "processing",
            }
            es.index_doc(f"documents_{bank_id}", doc_record, doc_id=doc_id, refresh=True)

            # Create samples with sys_chunk field
            samples = []
            for i, chunk_text in enumerate(chunks):
                sample_id = str(uuid.uuid4())
                sample_doc = _make_sys_fields(sample_id, doc_id, default_tpl_id)
                sample_doc.update(custom_field_defaults)
                sample_doc["sys_chunk"] = chunk_text
                samples.append((sample_id, sample_doc))

            # Bulk index samples
            sample_docs_for_es = [{"id": sid, **sdoc} for sid, sdoc in samples]
            es.bulk_index(f"samples_{bank_id}", sample_docs_for_es, id_field="id", refresh=True)

            # Embed chunks and insert into Vearch
            config = get_config()
            embedder = create_embedder(
                bank.get("embedding_backend", "triton"),
                bank.get("embedding_model", ""),
                config,
            )
            chunk_texts = [s[1]["sys_chunk"] for s in samples]
            embeddings = embedder.encode_batched(chunk_texts)

            # Collect vearch filter fields from non-default retrieval APIs (exclude sys_ fields)
            vearch_filter_fields = set()
            for api_def in bank.get("retrieval_apis", []):
                if api_def.get("is_default"):
                    continue
                for cond in api_def.get("search_conditions", []):
                    field = cond.get("field", "")
                    if field and cond.get("mode", "") != "vector" and not field.startswith("sys_"):
                        vearch_filter_fields.add(field)

            # Insert into Vearch
            vearch_docs = []
            for idx, (sample_id, sample_doc) in enumerate(samples):
                vearch_entry = {
                    "sys_chunk_vector": {"feature": [float(x) for x in embeddings[idx]]},
                    "sys_sample_id": sample_id,
                    "sys_document_id": doc_id,
                }
                for ff in vearch_filter_fields:
                    if ff in sample_doc:
                        vearch_entry[ff] = sample_doc[ff]
                vearch_docs.append((sample_id, vearch_entry))

            space_name = vearch_space_name(bank_id)
            vearch.bulk_insert(space_name, vearch_docs, refresh=True)

            # Update document status
            es.update_doc(
                f"documents_{bank_id}",
                doc_id,
                {"status": "completed"},
                refresh=True,
            )

            await _publish_sample_events(request, bank_id, sample_docs_for_es)

            return {
                "id": doc_id,
                "bank_id": bank_id,
                "filename": filename,
                "file_type": file_type,
                "sample_count": len(chunks),
                "status": "completed",
            }

        # -------------------------------------------------------------------
        # Case 2: Spreadsheet files (xlsx/csv)
        # -------------------------------------------------------------------
        elif ext in SPREADSHEET_FILE_TYPES:
            from app.services import sample_service

            rows: list[dict] = []

            if ext == "csv":
                text = content.decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    rows.append(dict(row))

            elif ext == "xlsx":
                import openpyxl

                wb = openpyxl.load_workbook(
                    filename=io.BytesIO(content), read_only=True, data_only=True
                )
                ws = wb.active
                if ws is not None:
                    row_iter = ws.iter_rows(values_only=True)
                    headers_row = next(row_iter, None)
                    if headers_row:
                        headers = [
                            str(h).strip() if h is not None else f"col_{i}"
                            for i, h in enumerate(headers_row)
                        ]
                        for data_row in row_iter:
                            row_dict = {}
                            for i, cell_value in enumerate(data_row):
                                if i < len(headers):
                                    row_dict[headers[i]] = (
                                        str(cell_value) if cell_value is not None else ""
                                    )
                            rows.append(row_dict)
                wb.close()

            # Validate columns against bank schema
            schema_fields = bank.get("schema", {}).get("fields", [])
            if schema_fields:
                schema_field_names = {f["name"] for f in schema_fields if isinstance(f, dict)}
                if rows:
                    file_columns = set(rows[0].keys())
                    unknown_columns = file_columns - schema_field_names - {
                        "sys_sample_id", "sys_document_id", "sys_template",
                        "sys_priority", "sys_status", "sys_executor",
                        "sys_overview", "sys_remarks", "sys_create_time",
                        "sys_update_time", "sys_chunk",
                    }
                    # Log unknown columns but do not reject - they may be extra
                    # columns the user wants to ignore

            # Create document record
            doc_id = str(uuid.uuid4())
            doc_record = {
                "id": doc_id,
                "bank_id": bank_id,
                "filename": filename,
                "file_type": file_type,
                "upload_time": datetime.now(timezone.utc).isoformat(),
                "uploaded_by": user["username"],
                "sample_count": len(rows),
                "status": "completed",
            }
            es.index_doc(f"documents_{bank_id}", doc_record, doc_id=doc_id, refresh=True)

            # Create samples from rows
            sample_docs = []
            for row in rows:
                sample_id = str(uuid.uuid4())
                sample_doc = _make_sys_fields(sample_id, doc_id, default_tpl_id)
                sample_doc["id"] = sample_id
                sample_doc.update(custom_field_defaults)
                sample_doc.update(row)
                sample_docs.append(sample_doc)

            if sample_docs:
                es.bulk_index(f"samples_{bank_id}", sample_docs, id_field="id", refresh=True)
                await _write_custom_vector_fields(bank, sample_docs, doc_id, vearch, bank_id)
                await _publish_sample_events(request, bank_id, sample_docs)

            return {
                "id": doc_id,
                "bank_id": bank_id,
                "filename": filename,
                "file_type": file_type,
                "sample_count": len(rows),
                "status": "completed",
            }

        # -------------------------------------------------------------------
        # Case 3: Text files without sys_chunk (store as single sample)
        # -------------------------------------------------------------------
        else:
            from app.services import sample_service

            doc_id = str(uuid.uuid4())
            doc_record = {
                "id": doc_id,
                "bank_id": bank_id,
                "filename": filename,
                "file_type": file_type,
                "upload_time": datetime.now(timezone.utc).isoformat(),
                "uploaded_by": user["username"],
                "sample_count": 1,
                "status": "completed",
            }
            es.index_doc(f"documents_{bank_id}", doc_record, doc_id=doc_id, refresh=True)

            sample_id = str(uuid.uuid4())
            sample_doc = _make_sys_fields(sample_id, doc_id, default_tpl_id)
            sample_doc["id"] = sample_id
            sample_doc.update(custom_field_defaults)
            sample_doc["content"] = content.decode("utf-8", errors="replace")
            es.index_doc(f"samples_{bank_id}", sample_doc, doc_id=sample_id, refresh=True)

            await _publish_sample_events(request, bank_id, [sample_doc])

            return {
                "id": doc_id,
                "bank_id": bank_id,
                "filename": filename,
                "file_type": file_type,
                "sample_count": 1,
                "status": "completed",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ---------------------------------------------------------------------------
# GET / - list documents
# ---------------------------------------------------------------------------
@router.get("")
async def list_documents(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import document_service

        result = document_service.list_documents(es, bank_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{doc_id} - get document detail
# ---------------------------------------------------------------------------
@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import document_service

        result = document_service.get_document(es, bank_id, doc_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# DELETE /{doc_id} - delete document and its samples
# ---------------------------------------------------------------------------
@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    vearch = request.app.state.vearch
    try:
        from app.services import document_service

        document_service.delete_document(es, vearch, bank_id, doc_id)
        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
