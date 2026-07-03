from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user, resolve_bank_id
from app.config import get_config
from app.embedder import create_embedder
from app.models.bank import RetrievalApiDef
from app.models.retrieval import RetrievalQuery
from app.services import bank_service

router = APIRouter()


# ---------------------------------------------------------------------------
# POST / - create retrieval API (stored in bank doc)
# ---------------------------------------------------------------------------
@router.post("")
async def create_retrieval_api(
    data: RetrievalApiDef,
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

        # Assign a new ID if not provided
        api_def = data.model_dump()
        if not api_def.get("id"):
            api_def["id"] = str(uuid.uuid4())

        # Append to existing retrieval_apis array
        retrieval_apis = bank.get("retrieval_apis", [])
        retrieval_apis.append(api_def)

        es.update_doc(
            "banks",
            bank_id,
            {"retrieval_apis": retrieval_apis},
            refresh=True,
        )

        return api_def
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET / - list retrieval APIs for bank
# ---------------------------------------------------------------------------
@router.get("")
async def list_retrieval_apis(
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

        return bank.get("retrieval_apis", [])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /{api_id} - update retrieval API
# ---------------------------------------------------------------------------
@router.put("/{api_id}")
async def update_retrieval_api(
    api_id: str,
    data: RetrievalApiDef,
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

        retrieval_apis = bank.get("retrieval_apis", [])
        found = False
        for i, api in enumerate(retrieval_apis):
            if api.get("id") == api_id:
                updated = data.model_dump()
                updated["id"] = api_id
                retrieval_apis[i] = updated
                found = True
                break

        if not found:
            raise HTTPException(status_code=404, detail="Retrieval API not found")

        es.update_doc(
            "banks",
            bank_id,
            {"retrieval_apis": retrieval_apis},
            refresh=True,
        )

        return retrieval_apis[i]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# DELETE /{api_id} - delete retrieval API
# ---------------------------------------------------------------------------
@router.delete("/{api_id}")
async def delete_retrieval_api(
    api_id: str,
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

        retrieval_apis = bank.get("retrieval_apis", [])
        original_len = len(retrieval_apis)
        retrieval_apis = [api for api in retrieval_apis if api.get("id") != api_id]

        if len(retrieval_apis) == original_len:
            raise HTTPException(status_code=404, detail="Retrieval API not found")

        es.update_doc(
            "banks",
            bank_id,
            {"retrieval_apis": retrieval_apis},
            refresh=True,
        )

        return {"message": "Retrieval API deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /{api_id}/query - execute retrieval
# ---------------------------------------------------------------------------
@router.post("/{api_id}/query")
async def execute_retrieval(
    api_id: str,
    query: RetrievalQuery,
    request: Request,
    bank_id: str = Depends(resolve_bank_id),
    user: dict = Depends(get_current_user),
):
    es = request.app.state.es
    vearch = request.app.state.vearch
    try:
        from app.services import retrieval_service

        bank = bank_service.get_bank(es, bank_id)
        if bank is None:
            raise HTTPException(status_code=404, detail="Bank not found")

        # Find the specific retrieval API definition
        retrieval_apis = bank.get("retrieval_apis", [])
        api_def = None
        for api in retrieval_apis:
            if api.get("id") == api_id:
                api_def = api
                break

        if api_def is None:
            raise HTTPException(status_code=404, detail="Retrieval API not found")

        # Create embedder for vector search
        config = get_config()
        embedder = create_embedder(
            bank.get("embedding_backend", "triton"),
            bank.get("embedding_model", ""),
            config,
        )

        result = retrieval_service.execute_retrieval(
            es=es,
            vearch=vearch,
            embedder=embedder,
            bank_id=bank_id,
            api_def=api_def,
            query_data=query.model_dump(),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
