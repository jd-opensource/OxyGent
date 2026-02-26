from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


_REPO_ROOT = _repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from oxygent import MAS, oxy  # noqa: E402
from oxygent.a2a import TaskStore, build_a2a_router  # noqa: E402


def _has_http_llm_env() -> bool:
    base_url = os.getenv("DEFAULT_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = os.getenv("DEFAULT_LLM_MODEL_NAME") or os.getenv("OPENAI_MODEL_NAME")
    return bool(base_url and model)


def _force_mock() -> bool:
    return os.getenv("A2A_FORCE_MOCK", "").strip().lower() in {"1", "true", "yes", "on"}


def _extract_user_text_from_messages(messages) -> str:
    if not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content.strip()
    return ""


async def _mock_worker_output(oxy_request):
    messages = oxy_request.arguments.get("messages") if hasattr(oxy_request, "arguments") else None
    user_text = _extract_user_text_from_messages(messages)
    return (
        "### Worker Result (OxyGent Mock)\n"
        "Status: completed\n\n"
        f"Input:\n{user_text}\n\n"
        "Output:\n- Done.\n"
    )


WORKER_PROMPT = (
    "You are a worker agent. Execute exactly the given step and return the result. "
    "If inputs are missing, ask a single clarifying question. Keep output concise."
)


oxy_space = [
    (
        oxy.HttpLLM(
            name="default_llm",
            api_key=os.getenv("DEFAULT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME") or os.getenv("OPENAI_MODEL_NAME"),
        )
        if (_has_http_llm_env() and not _force_mock())
        else oxy.MockLLM(name="default_llm", func_mock_process=_mock_worker_output)
    ),
    oxy.ChatAgent(
        name="master_agent",
        desc="OxyGent A2A worker agent",
        llm_model="default_llm",
        prompt=os.getenv("A2A_SYSTEM_PROMPT", WORKER_PROMPT),
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        a2a_router = build_a2a_router(mas=mas, store=TaskStore())
        await mas.start_web_service(
            first_query="hello",
            host=os.getenv("A2A_HOST", "127.0.0.1"),
            port=int(os.getenv("A2A_PORT", "8000")),
            routers=[a2a_router],
        )


if __name__ == "__main__":
    asyncio.run(main())
