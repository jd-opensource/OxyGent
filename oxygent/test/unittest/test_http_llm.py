"""
Unit tests for HttpLLM
"""

import pytest

from oxygent.oxy.llms.http_llm import HttpLLM
from oxygent.schemas import OxyRequest, OxyState, OxyResponse


# ──────────────────────────────────────────────────────────────────────────────
# Helper: mock Config.get_llm_config() 
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def config_patch(monkeypatch):
    monkeypatch.setattr(
        "oxygent.oxy.llms.http_llm.Config.get_llm_config", lambda: {}, raising=True
    )


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def llm(monkeypatch):
    async def passthrough(self, req: OxyRequest):
        return req.arguments["messages"]

    monkeypatch.setattr(
        "oxygent.oxy.llms.base_llm.BaseLLM._get_messages", passthrough, raising=True
    )

    return HttpLLM(
        name="http_llm",
        desc="UT HTTP LLM",
        api_key="sk-123",
        base_url="https://api.fake.com/v1/chat",
        model_name="gpt-ut",
        llm_params={"temperature": 0.3},
    )


@pytest.fixture
def oxy_request():
    return OxyRequest(
        arguments={
            "messages": [
                {"role": "user", "content": "Hello, LLM"},
            ],
            "top_p": 0.9,
        },
        caller="tester",
        caller_category="agent",
        current_trace_id="trace123",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_execute_success(monkeypatch, llm, oxy_request):
    captured = {}

    # ----- mock httpx.AsyncClient ------------------------------------------------
    class FakeResponse:
        def json(self):
            return {
                "choices": [
                    {"message": {"content": "Hi there!"}}
                ]
            }

        def raise_for_status(self):
            pass

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr("oxygent.oxy.llms.http_llm.httpx.AsyncClient", lambda *a, **k: FakeClient())

    # ---------------------------------------------------------------------------
    resp: OxyResponse = await llm._execute(oxy_request)

    assert resp.state is OxyState.COMPLETED
    assert resp.output == "Hi there!"

    assert captured["url"] == "https://api.fake.com/v1/chat"
    assert captured["headers"]["Authorization"] == "Bearer sk-123"

    pay = captured["payload"]
    assert pay["model"] == "gpt-ut"
    assert pay["temperature"] == 0.3            # llm_params
    assert pay["top_p"] == 0.9                 
    assert pay["messages"][0]["content"] == "Hello, LLM"


@pytest.mark.asyncio
async def test_execute_http_error(monkeypatch, llm, oxy_request):

    class FakeErrResponse(Exception):
        pass

    class ErrResp:
        def raise_for_status(self):
            raise FakeErrResponse("401")

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, *a, **kw):
            return ErrResp()

    monkeypatch.setattr(
        "oxygent.oxy.llms.http_llm.httpx.AsyncClient", lambda *a, **k: FakeClient()
    )

    with pytest.raises(FakeErrResponse):
        await llm._execute(oxy_request)

