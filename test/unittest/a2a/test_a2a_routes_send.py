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
        req = OxyRequest()
        req.current_trace_id = payload.get("current_trace_id", "")
        req.group_id = payload.get("group_id", "")
        req.request_id = payload.get("request_id", "")
        return OxyResponse(state=OxyState.COMPLETED, output="ok", oxy_request=req)

    async def event_stream(self, redis_key, current_trace_id, task):
        raise RuntimeError("not used")


@pytest.mark.asyncio
async def test_message_send_returns_task():
    mas = FakeMAS()
    app = FastAPI()
    app.include_router(build_a2a_router(mas=mas, store=TaskStore()))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/message:send",
            json={
                "message": {
                    "kind": "message",
                    "messageId": "m1",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "hi"}],
                }
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "task" in body
        assert body["task"]["id"]
        assert body["task"]["status"]["state"] == "completed"
