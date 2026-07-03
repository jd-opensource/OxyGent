from __future__ import annotations

from pydantic import BaseModel
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user, require_admin
from app.config import get_config

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AnnotationConfigUpdate(BaseModel):
    max_concurrency: int


class EmbeddingConfigUpdate(BaseModel):
    triton_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None


class ChunkingConfigUpdate(BaseModel):
    chunk_size: int
    chunk_overlap: int


# ---------------------------------------------------------------------------
# GET / - get current config (sanitized, no passwords)
# ---------------------------------------------------------------------------
@router.get("")
async def get_current_config(
    user: dict = Depends(get_current_user),
):
    try:
        config = get_config()

        # Return sanitized config (no secrets)
        return {
            "elasticsearch": {
                "hosts": config.es.hosts,
                "index_prefix": config.es.index_prefix,
                "timeout": config.es.timeout,
            },
            "vearch": {
                "master_url": config.vearch.master_url,
                "router_url": config.vearch.router_url,
                "db_name": config.vearch.db_name,
            },
            "triton": {
                "url": config.triton.url,
                "batch_size": config.triton.batch_size,
                "max_concurrent": config.triton.max_concurrent,
            },
            "openai_embedding": {
                "base_url": config.openai.base_url,
                "model": config.openai.model,
                "batch_size": config.openai.batch_size,
                "max_concurrent": config.openai.max_concurrent,
            },
            "llm": {
                "base_url": config.llm.base_url,
                "model": config.llm.model,
            },
            "annotation": {
                "max_concurrency": config.annotation.max_concurrency,
                "max_cascade_depth": config.annotation.max_cascade_depth,
                "agent_timeout": config.annotation.agent_timeout,
                "event_queue_size": config.annotation.event_queue_size,
            },
            "chunking": {
                "chunk_size": config.chunking.chunk_size,
                "chunk_overlap": config.chunking.chunk_overlap,
            },
            "server": {
                "host": config.server.host,
                "port": config.server.port,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /annotation - update annotation concurrency
# ---------------------------------------------------------------------------
@router.put("/annotation")
async def update_annotation_config(
    data: AnnotationConfigUpdate,
    request: Request,
    user: dict = Depends(require_admin),
):
    try:
        config = get_config()
        dispatcher = request.app.state.dispatcher

        # Update config
        config.annotation.max_concurrency = data.max_concurrency

        # Update dispatcher semaphore
        dispatcher.set_concurrency(data.max_concurrency)

        return {"message": "Annotation config updated", "max_concurrency": data.max_concurrency}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /embedding - update embedding config
# ---------------------------------------------------------------------------
@router.put("/embedding")
async def update_embedding_config(
    data: EmbeddingConfigUpdate,
    user: dict = Depends(require_admin),
):
    try:
        config = get_config()

        if data.triton_url is not None:
            config.triton.url = data.triton_url
        if data.openai_api_key is not None:
            config.openai.api_key = data.openai_api_key
        if data.openai_base_url is not None:
            config.openai.base_url = data.openai_base_url
        if data.openai_model is not None:
            config.openai.model = data.openai_model

        return {"message": "Embedding config updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /chunking - update chunking config
# ---------------------------------------------------------------------------
@router.put("/chunking")
async def update_chunking_config(
    data: ChunkingConfigUpdate,
    user: dict = Depends(require_admin),
):
    try:
        config = get_config()

        config.chunking.chunk_size = data.chunk_size
        config.chunking.chunk_overlap = data.chunk_overlap

        return {
            "message": "Chunking config updated",
            "chunk_size": data.chunk_size,
            "chunk_overlap": data.chunk_overlap,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
