from __future__ import annotations

import json
from typing import Any, Optional, Tuple

from ..schemas import OxyResponse, OxyState
from ..utils.common_utils import generate_uuid
from .schemas import (
    Artifact,
    Message,
    MessageSendRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)


def _safe_json_loads(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def extract_text_from_parts(parts: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for p in parts or []:
        if not isinstance(p, dict):
            continue
        kind = p.get("kind") or p.get("type")
        if kind == "text":
            text = p.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks)


def rest_request_to_oxy_payload(
    req: MessageSendRequest,
    *,
    master_agent_name: str,
    override_callee: Optional[str] = None,
) -> Tuple[dict[str, Any], str, str]:
    msg = req.message
    task_id = msg.taskId or generate_uuid()
    context_id = msg.contextId or generate_uuid()

    query = extract_text_from_parts(msg.parts)

    payload: dict[str, Any] = {
        "query": query,
        "request_id": msg.messageId,
        "current_trace_id": task_id,
        "group_id": context_id,
        "shared_data": {
            "_a2a": {
                "raw": req.model_dump(mode="python", exclude_none=True),
            }
        },
    }

    callee = override_callee or master_agent_name
    if callee:
        payload["callee"] = callee
    return payload, task_id, context_id


def _task_state_from_oxy_state(state: OxyState) -> TaskState:
    if state == OxyState.COMPLETED:
        return TaskState.completed
    if state == OxyState.CANCELED:
        return TaskState.canceled
    if state == OxyState.FAILED:
        return TaskState.failed
    return TaskState.unknown


def build_agent_message(*, text: str, task_id: str, context_id: str) -> Message:
    return Message(
        role="agent",
        messageId=generate_uuid(),
        taskId=task_id,
        contextId=context_id,
        parts=[TextPart(text=text).model_dump(mode="python", exclude_none=True)],
    )


def oxy_response_to_task(oxy_response: OxyResponse, *, task_id: str, context_id: str) -> Task:
    state = _task_state_from_oxy_state(oxy_response.state)
    msg = build_agent_message(text=str(oxy_response.output), task_id=task_id, context_id=context_id)
    status = TaskStatus(state=state, message=msg)
    artifact = Artifact(
        artifactId=f"{task_id}:output",
        name="output",
        parts=[TextPart(text=str(oxy_response.output)).model_dump(mode="python")],
    )
    return Task(id=task_id, contextId=context_id, status=status, artifacts=[artifact])


def new_task(*, task_id: str, context_id: str, state: TaskState) -> Task:
    return Task(
        id=task_id,
        contextId=context_id,
        status=TaskStatus(state=state),
        artifacts=[],
    )


def mas_sse_dict_to_a2a_update(
    sse: dict[str, Any],
    *,
    task_id: str,
    context_id: str,
    artifact_id: str,
    terminal_state: TaskState = TaskState.completed,
) -> Optional[dict[str, Any]]:
    event = sse.get("event", "message")
    if event == "close":
        status_update = TaskStatusUpdateEvent(
            taskId=task_id,
            contextId=context_id,
            status=TaskStatus(state=terminal_state),
            final=True,
        )
        return {"statusUpdate": status_update.model_dump(mode="python", exclude_none=True)}

    data = _safe_json_loads(sse.get("data"))
    if not isinstance(data, dict):
        return None
    msg_type = data.get("type")

    if msg_type == "stream":
        delta = (
            (data.get("content") or {}).get("delta")
            if isinstance(data.get("content"), dict)
            else None
        )
        if not isinstance(delta, str) or not delta:
            return None
        artifact_update = TaskArtifactUpdateEvent(
            taskId=task_id,
            contextId=context_id,
            append=True,
            artifact=Artifact(
                artifactId=artifact_id,
                parts=[TextPart(text=delta).model_dump(mode="python")],
            ),
        )
        return {"artifactUpdate": artifact_update.model_dump(mode="python", exclude_none=True)}

    if msg_type == "answer":
        content = data.get("content")
        if not isinstance(content, str) or not content:
            return None
        artifact_update = TaskArtifactUpdateEvent(
            taskId=task_id,
            contextId=context_id,
            append=False,
            lastChunk=True,
            artifact=Artifact(
                artifactId=artifact_id,
                parts=[TextPart(text=content).model_dump(mode="python")],
            ),
        )
        return {"artifactUpdate": artifact_update.model_dump(mode="python", exclude_none=True)}

    return None
