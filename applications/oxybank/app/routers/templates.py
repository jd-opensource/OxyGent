from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_user, require_admin, resolve_bank_id
from app.models.template import (
    LLMChatRequest,
    TemplateCreate,
    TemplateTestRequest,
    TemplateUpdate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET / - list templates for bank
# ---------------------------------------------------------------------------
@router.get("")
async def list_templates(
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import template_service

        result = template_service.list_templates(es, bank_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST / - create template
# ---------------------------------------------------------------------------
@router.post("")
async def create_template(
    data: TemplateCreate,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    try:
        from app.services import template_service

        result = template_service.create_template(es, bank_id, data.model_dump(), user.get("username", ""))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{template_id} - get template
# ---------------------------------------------------------------------------
@router.get("/{template_id}")
async def get_template(
    template_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import template_service

        result = template_service.get_template(es, bank_id, template_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Template not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /{template_id} - update template
# ---------------------------------------------------------------------------
@router.put("/{template_id}")
async def update_template(
    template_id: str,
    data: TemplateUpdate,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    try:
        from app.services import template_service

        result = template_service.update_template(es, template_id, data.model_dump(exclude_none=True))
        if result is None:
            raise HTTPException(status_code=404, detail="Template not found")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# DELETE /{template_id} - delete template
# ---------------------------------------------------------------------------
@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(require_admin),
):
    es = request.app.state.es
    try:
        from app.services import template_service

        template_service.delete_template(es, bank_id, template_id)
        return {"message": "Template deleted successfully"}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /generate - LLM chat (SSE streaming)
# ---------------------------------------------------------------------------
@router.post("/generate")
async def llm_chat(
    data: LLMChatRequest,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    try:
        from app.services import template_service
        from app.config import get_config

        config = get_config()
        messages = [{"role": m.role, "content": m.content} for m in data.messages]
        stream = template_service.llm_chat(config, messages, data.bank_schema, data.current_template)

        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /{template_id}/test - test template
# ---------------------------------------------------------------------------
@router.post("/{template_id}/test")
async def test_template(
    template_id: str,
    data: TemplateTestRequest,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    try:
        from app.services import template_service

        result = template_service.test_template(es, bank_id, template_id, data)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
