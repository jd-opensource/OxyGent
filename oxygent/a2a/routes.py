from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ..mas import MAS
from .agent_card import build_agent_card
from .mapping import (
    mas_sse_dict_to_a2a_update,
    new_task,
    oxy_response_to_task,
    rest_request_to_oxy_payload,
)
from .schemas import MessageSendRequest, TaskState
from .task_store import TaskStore


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def build_a2a_router(
    *,
    mas: MAS,
    store: Optional[TaskStore] = None,
    a2a_prefix: str = "",
) -> APIRouter:
    store = store or TaskStore()
    router = APIRouter()

    @router.get("/.well-known/agent-card.json")
    async def get_agent_card(request: Request):
        card = build_agent_card(request=request, a2a_prefix=a2a_prefix)
        return card.model_dump(mode="python", exclude_none=True)

    @router.post(f"{a2a_prefix}/v1/message:send")
    async def message_send(req: MessageSendRequest, request: Request):
        override_callee = None
        if req.metadata and isinstance(req.metadata, dict):
            override_callee = req.metadata.get("oxygent.callee")

        payload, task_id, context_id = rest_request_to_oxy_payload(
            req,
            master_agent_name=mas.master_agent_name,
            override_callee=override_callee,
        )

        store.upsert(new_task(task_id=task_id, context_id=context_id, state=TaskState.working))
        oxy_resp = await mas.chat_with_agent(payload=payload)
        task = oxy_response_to_task(oxy_resp, task_id=task_id, context_id=context_id)
        store.upsert(task)
        return {"task": task.model_dump(mode="python", exclude_none=True)}

    @router.post(f"{a2a_prefix}/v1/message:stream")
    async def message_stream(req: MessageSendRequest, request: Request):
        override_callee = None
        if req.metadata and isinstance(req.metadata, dict):
            override_callee = req.metadata.get("oxygent.callee")

        payload, task_id, context_id = rest_request_to_oxy_payload(
            req,
            master_agent_name=mas.master_agent_name,
            override_callee=override_callee,
        )

        artifact_id = f"{task_id}:stream"
        store.upsert(new_task(task_id=task_id, context_id=context_id, state=TaskState.submitted))

        redis_key = f"{mas.message_prefix}:{mas.name}:{task_id}"
        bg_task = asyncio.create_task(
            mas.chat_with_agent(payload=payload, send_msg_key=redis_key)
        )

        async def gen():
            store.upsert(new_task(task_id=task_id, context_id=context_id, state=TaskState.working))
            yield {"data": _dump({"task": store.get(task_id).model_dump(mode="python", exclude_none=True)})}

            terminal_state = TaskState.completed
            if store.is_canceled(task_id):
                terminal_state = TaskState.canceled

            async for sse in mas.event_stream(redis_key, task_id, bg_task):
                if store.is_canceled(task_id):
                    terminal_state = TaskState.canceled
                update = mas_sse_dict_to_a2a_update(
                    sse,
                    task_id=task_id,
                    context_id=context_id,
                    artifact_id=artifact_id,
                    terminal_state=terminal_state,
                )
                if update is None:
                    continue
                artifact_update = update.get("artifactUpdate")
                if isinstance(artifact_update, dict):
                    try:
                        part = (
                            artifact_update.get("artifact", {})
                            .get("parts", [{}])[0]
                            .get("text")
                        )
                        if isinstance(part, str) and part:
                            store.append_text(task_id, part)
                    except Exception:
                        pass
                if "statusUpdate" in update:
                    store_task = store.get(task_id)
                    if store_task:
                        store_task.status.state = terminal_state
                        store.upsert(store_task)
                yield {"data": _dump(update)}

        return EventSourceResponse(gen())

    @router.get(f"{a2a_prefix}/v1/tasks/{{task_id}}")
    async def tasks_get(task_id: str, historyLength: Optional[int] = None):
        task = store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task.model_dump(mode="python", exclude_none=True)

    @router.get(f"{a2a_prefix}/v1/tasks")
    async def tasks_list(contextId: Optional[str] = None, limit: int = 50):
        tasks = store.list(context_id=contextId, limit=limit)
        return {
            "tasks": [t.model_dump(mode="python", exclude_none=True) for t in tasks],
            "nextPageToken": "",
        }

    @router.post(f"{a2a_prefix}/v1/tasks/{{task_id}}:cancel")
    async def tasks_cancel(task_id: str):
        task = store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")

        store.mark_canceled(task_id)
        active = mas.active_tasks.get(task_id)
        if active is not None:
            active.cancel()
        task = store.get(task_id)
        return task.model_dump(mode="python", exclude_none=True)

    return router
