import asyncio
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from oxygent import MAS, oxy  # noqa: E402
from oxygent.a2a import TaskStore, build_a2a_router  # noqa: E402


def _has_http_llm_env() -> bool:
    base_url = os.getenv("DEFAULT_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = os.getenv("DEFAULT_LLM_MODEL_NAME") or os.getenv("OPENAI_MODEL_NAME")
    return bool(base_url and model)


async def _mock_a2a_output(_oxy_request):
    return (
        "### Mock Reply (OxyGent A2A)\n"
        "This is a deterministic mock response because no HTTP LLM env is configured.\n"
    )


oxy_space = [
    (
        oxy.HttpLLM(
            name="default_llm",
            api_key=os.getenv("DEFAULT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME") or os.getenv("OPENAI_MODEL_NAME"),
        )
        if _has_http_llm_env()
        else oxy.MockLLM(name="default_llm", func_mock_process=_mock_a2a_output)
    ),
    oxy.ChatAgent(
        name="master_agent",
        desc="OxyGent master agent",
        llm_model="default_llm",
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
