from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.dependencies import get_current_user, require_admin, resolve_bank_id
from app.models.annotation import AgentCreate, AgentUpdate

router = APIRouter()


@router.get("")
async def list_agents(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        query = {"bool": {"filter": [{"term": {"bank_id": bank_id}}]}}
        result = es.search("agents", query=query, size=100)
        return result.get("items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _validate_agent_shape(kind: str, service_url: str, steps: list) -> None:
    """Guard against saving a half-configured agent (URL-mode without url,
    inline-mode without steps, unknown kind). Runner-level step validation
    lives in annotation_service.run_inline_agent — we only sanity-check that
    the right container is filled here."""
    if kind not in ("url", "inline"):
        raise HTTPException(status_code=400, detail=f"Unsupported agent kind: {kind!r}")
    if kind == "url" and not service_url:
        raise HTTPException(status_code=400, detail="service_url is required for URL agents")
    if kind == "inline" and not steps:
        raise HTTPException(status_code=400, detail="steps must be non-empty for inline agents")


@router.post("")
async def create_agent(
    data: AgentCreate,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    dispatcher = request.app.state.dispatcher
    try:
        _validate_agent_shape(data.kind, data.service_url, data.steps)
        agent_id = str(uuid.uuid4())
        agent_doc = {
            "id": agent_id,
            "bank_id": bank_id,
            "name": data.name,
            "kind": data.kind,
            "service_url": data.service_url,
            "steps": data.steps,
            "trigger_statuses": data.trigger_statuses,
            "enabled": True,
            "created_by": user["username"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        es.index_doc("agents", agent_doc, doc_id=agent_id, refresh=True)
        await dispatcher.reload_agents()
        await dispatcher.scan_existing_samples(agent_doc)
        return agent_doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    dispatcher = request.app.state.dispatcher
    try:
        existing = es.get_doc("agents", agent_id)
        if existing is None or existing.get("bank_id") != bank_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        update_fields = {}
        if data.name is not None:
            update_fields["name"] = data.name
        if data.kind is not None:
            update_fields["kind"] = data.kind
        if data.service_url is not None:
            update_fields["service_url"] = data.service_url
        if data.steps is not None:
            update_fields["steps"] = data.steps
        if data.trigger_statuses is not None:
            update_fields["trigger_statuses"] = data.trigger_statuses
        if data.enabled is not None:
            update_fields["enabled"] = data.enabled
        # Re-validate the merged shape so partial updates can't leave the agent broken
        # (e.g. switching kind=inline without providing steps).
        merged_kind = update_fields.get("kind", existing.get("kind", "url"))
        merged_url = update_fields.get("service_url", existing.get("service_url", ""))
        merged_steps = update_fields.get("steps", existing.get("steps", []))
        _validate_agent_shape(merged_kind, merged_url, merged_steps)
        if update_fields:
            update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            es.update_doc("agents", agent_id, update_fields, refresh=True)
        await dispatcher.reload_agents()

        # Scan existing samples when agent is enabled or trigger_statuses changed
        was_enabled = existing.get("enabled", False)
        now_enabled = update_fields.get("enabled", was_enabled)
        statuses_changed = "trigger_statuses" in update_fields
        if now_enabled and (not was_enabled or statuses_changed):
            updated_agent = es.get_doc("agents", agent_id)
            if updated_agent:
                await dispatcher.scan_existing_samples(updated_agent)

        return es.get_doc("agents", agent_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    dispatcher = request.app.state.dispatcher
    try:
        existing = es.get_doc("agents", agent_id)
        if existing is None or existing.get("bank_id") != bank_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        es.delete_doc("agents", agent_id, refresh=True)
        await dispatcher.reload_agents()
        return {"message": "Agent deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def list_agent_logs(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    agent_id: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        filters = [{"term": {"bank_id": bank_id}}]
        if agent_id:
            filters.append({"term": {"agent_id": agent_id}})
        if success is not None:
            filters.append({"term": {"success": success}})
        query = {"bool": {"filter": filters}}
        from_ = (page - 1) * size
        result = es.search(
            "agent_logs", query=query, size=size, from_=from_,
            sort=[{"timestamp": {"order": "desc"}}],
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
