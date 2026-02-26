import asyncio
import json

import pytest
from fastapi import FastAPI
import httpx

from oxygent.a2a import TaskStore, build_a2a_router
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


class FakeMAS:
    def __init__(self):
        self.message_prefix = "oxygent"
        self.name = "test"
        self.master_agent_name = "master_agent"
        self.active_tasks = {}

    async def chat_with_agent(self, payload=None, send_msg_key: str = ""):
        await asyncio.sleep(0)
        req = OxyRequest()
        req.current_trace_id = payload.get("current_trace_id", "")
        req.group_id = payload.get("group_id", "")
        req.request_id = payload.get("request_id", "")
        return OxyResponse(state=OxyState.COMPLETED, output="ok", oxy_request=req)

    async def event_stream(self, redis_key, current_trace_id, task):
        yield {
            "event": "message",
            "data": json.dumps({"type": "stream", "content": {"delta": "Hel"}}),
        }
        yield {
            "event": "message",
            "data": json.dumps({"type": "stream", "content": {"delta": "lo"}}),
        }
        yield {"event": "close", "data": "done"}


@pytest.mark.asyncio
async def test_message_stream_sse_sequence():
    mas = FakeMAS()
    app = FastAPI()
    app.include_router(build_a2a_router(mas=mas, store=TaskStore()))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/v1/message:stream",
            json={
                "message": {
                    "kind": "message",
                    "messageId": "m1",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "hi"}],
                }
            },
        ) as resp:
            assert resp.status_code == 200
            data_payloads = []
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data_payloads.append(json.loads(line[5:].strip()))
                if len(data_payloads) >= 4:
                    break

        assert "task" in data_payloads[0]
        assert any("artifactUpdate" in p for p in data_payloads)
        assert any("statusUpdate" in p and p["statusUpdate"]["final"] for p in data_payloads)
