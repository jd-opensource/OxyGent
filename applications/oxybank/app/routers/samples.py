from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.dependencies import get_current_user, resolve_bank_id
from app.models.sample import SampleUpdate

router = APIRouter()


# ---------------------------------------------------------------------------
# GET / - list samples (paginated, filterable)
# ---------------------------------------------------------------------------
@router.get("")
async def list_samples(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=200, description="Page size"),
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    executor: Optional[str] = Query(None, description="Filter by executor"),
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import sample_service

        result = sample_service.list_samples(
            es,
            bank_id,
            query_params={
                "page": page,
                "size": size,
                "doc_id": document_id,
                "status": status,
                "executor": executor,
            },
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /statuses - list all distinct sys_status values in this bank (with counts)
# ---------------------------------------------------------------------------
@router.get("/statuses")
async def list_statuses(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
    executor: Optional[str] = Query(None, description="Only count samples for this executor"),
):
    """Return distinct sys_status values in the bank (plus their doc counts). Used by
    the annotation page's status filter dropdown and progress bar, so the UI can
    display exactly the statuses in play — including any custom values users have
    introduced (e.g. '已发布', '已忽略') instead of a hard-coded set.

    Optional `executor` param scopes counts to that executor (annotators only see
    samples assigned to them)."""
    es = request.app.state.es
    try:
        query = None
        if executor:
            query = {"term": {"sys_executor": executor}}
        buckets = es.terms_aggregation(
            f"samples_{bank_id}",
            field="sys_status",
            query=query,
            size=100,
        )
        return {"items": buckets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /random - fetch one random sample from the bank (used by template tester)
# ---------------------------------------------------------------------------
@router.get("/random")
async def random_sample(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    """Return one randomly-picked sample from this bank. Used by the template test
    panel so the annotator doesn't need to hand-craft test JSON.
    Returns 404 if the bank has no samples yet."""
    es = request.app.state.es
    try:
        # ES 'function_score.random_score' picks a random doc without loading the full set.
        result = es.search(
            f"samples_{bank_id}",
            query={
                "function_score": {
                    "query": {"match_all": {}},
                    "random_score": {},
                }
            },
            size=1,
        )
        items = result.get("items", [])
        if not items:
            raise HTTPException(status_code=404, detail="No samples in this bank")
        return items[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{sample_id} - get sample
# ---------------------------------------------------------------------------
@router.get("/{sample_id}")
async def get_sample(
    sample_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import sample_service

        result = sample_service.get_sample(es, bank_id, sample_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Sample not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /{sample_id} - update sample
# ---------------------------------------------------------------------------
@router.put("/{sample_id}")
async def update_sample(
    sample_id: str,
    data: SampleUpdate,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    event_bus = request.app.state.event_bus
    try:
        from app.services import sample_service

        fields = dict(data.fields) if data.fields else {}

        existing = sample_service.get_sample(es, bank_id, sample_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Sample not found")

        # Save current state to sys_prev_*
        fields["sys_prev_status"] = existing.get("sys_status", "")
        fields["sys_prev_template"] = existing.get("sys_template", "")
        fields["sys_prev_executor"] = existing.get("sys_executor", "")

        # Advance to sys_next_* if set, otherwise keep current
        next_status = existing.get("sys_next_status", "")
        next_template = existing.get("sys_next_template", "")
        next_executor = existing.get("sys_next_executor", "")
        if next_status:
            fields["sys_status"] = next_status
        if next_template:
            fields["sys_template"] = next_template
        if next_executor:
            fields["sys_executor"] = next_executor

        # Clear sys_next_* after consuming
        fields["sys_next_status"] = ""
        fields["sys_next_template"] = ""
        fields["sys_next_executor"] = ""

        result = await sample_service.update_sample(
            es=es,
            bank_id=bank_id,
            sample_id=sample_id,
            changes=fields,
            user=user.get("username", ""),
            event_bus=event_bus,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /{sample_id}/reject - reject: revert to previous state
# ---------------------------------------------------------------------------
@router.put("/{sample_id}/reject")
async def reject_sample(
    sample_id: str,
    data: SampleUpdate,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    event_bus = request.app.state.event_bus
    try:
        from app.services import sample_service

        existing = sample_service.get_sample(es, bank_id, sample_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Sample not found")

        fields = {}

        # Revert to sys_prev_*
        prev_status = existing.get("sys_prev_status", "")
        prev_template = existing.get("sys_prev_template", "")
        prev_executor = existing.get("sys_prev_executor", "")
        if prev_status:
            fields["sys_status"] = prev_status
        if prev_template:
            fields["sys_template"] = prev_template
        if prev_executor:
            fields["sys_executor"] = prev_executor

        # Set remarks
        if data.remarks:
            fields["sys_remarks"] = data.remarks

        result = await sample_service.update_sample(
            es=es,
            bank_id=bank_id,
            sample_id=sample_id,
            changes=fields,
            user=user.get("username", ""),
            event_bus=event_bus,
        )
        return result
    except HTTPException:

        result = await sample_service.update_sample(
            es=es,
            bank_id=bank_id,
            sample_id=sample_id,
            changes=fields,
            user=user.get("username", ""),
            event_bus=event_bus,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# DELETE /{sample_id} - delete sample
# ---------------------------------------------------------------------------
@router.delete("/{sample_id}")
async def delete_sample(
    sample_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    vearch = request.app.state.vearch
    try:
        from app.services import sample_service

        sample_service.delete_sample(es, vearch, bank_id, sample_id)
        return {"message": "Sample deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{sample_id}/history - get modification history
# ---------------------------------------------------------------------------
@router.get("/{sample_id}/history")
async def get_sample_history(
    sample_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import sample_service

        result = sample_service.get_sample_history(es, bank_id, sample_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
