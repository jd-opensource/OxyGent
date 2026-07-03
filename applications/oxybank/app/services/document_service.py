from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.storage.es_client import ESClient
from app.storage.vearch_client import VearchClient, vearch_space_name

logger = logging.getLogger("oxybank.document_service")


def create_document(
    es: ESClient,
    bank_id: str,
    filename: str,
    file_type: str,
    user: str,
) -> dict:
    """Create a document record in the per-bank documents index."""
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "bank_id": bank_id,
        "filename": filename,
        "file_type": file_type,
        "upload_time": now,
        "uploaded_by": user,
        "sample_count": 0,
        "status": "active",
    }

    es.index_doc(f"documents_{bank_id}", doc, doc_id=doc_id, refresh=True)
    doc["id"] = doc_id
    return doc


def list_documents(
    es: ESClient,
    bank_id: str,
    page: int = 1,
    size: int = 20,
) -> dict:
    """Return a paginated list of documents for a bank.

    Returns ``{"total": int, "items": list[dict], "page": int, "size": int}``.
    """
    from_ = (max(page, 1) - 1) * size
    result = es.search(
        f"documents_{bank_id}",
        size=size,
        from_=from_,
        sort=[{"upload_time": {"order": "desc"}}],
    )
    return {
        "total": result["total"],
        "items": result["items"],
        "page": page,
        "size": size,
    }


def get_document(es: ESClient, bank_id: str, doc_id: str) -> dict | None:
    """Return a single document or None."""
    return es.get_doc(f"documents_{bank_id}", doc_id)


def delete_document(
    es: ESClient,
    vearch: VearchClient,
    bank_id: str,
    doc_id: str,
) -> bool:
    """Delete a document and all its samples from ES and Vearch."""
    # Delete all samples belonging to this document from ES
    es.delete_by_query(
        f"samples_{bank_id}",
        {"term": {"sys_document_id": doc_id}},
        refresh=True,
    )

    # Delete matching history entries
    es.delete_by_query(
        f"sample_history_{bank_id}",
        {"match_all": {}},  # history doesn't store doc_id directly; clean up via samples
        refresh=False,
    )

    # Delete matching vectors from Vearch
    space_name = vearch_space_name(bank_id)
    try:
        vearch.delete_by_query(
            space_name,
            [{"term": {"sys_document_id": [doc_id]}}],
        )
    except Exception as exc:
        logger.error("Vearch delete_by_query failed for doc %s: %s", doc_id, exc)

    # Delete the document record itself
    return es.delete_doc(f"documents_{bank_id}", doc_id, refresh=True)


def update_document_count(
    es: ESClient,
    bank_id: str,
    doc_id: str,
    count: int,
) -> None:
    """Update the sample_count field of a document."""
    es.update_doc(f"documents_{bank_id}", doc_id, {"sample_count": count}, refresh=True)
