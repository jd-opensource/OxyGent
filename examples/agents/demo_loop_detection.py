"""Demo: tool-call loop detection for ReAct agents.

Shows how to enable `loop_detection_mode` on a ReActAgent so that repeated or
cyclic tool calls are caught and either (a) force the agent to receive a
system-level hint and continue (``warn``), or (b) terminate the ReAct loop and
return a configurable message to the caller (``block`` / ``fallback``).

The ``buggy_search`` tool below always returns the same "no result" payload,
which forces any naive agent into a repeat loop. With detection enabled, the
agent stops after N identical calls instead of exhausting ``max_react_rounds``.
"""

import asyncio
import os

from oxygent import MAS, Config, oxy

Config.set_agent_short_memory_size(7)


def buggy_search(query: str) -> str:
    """A tool that always returns the same empty-result payload.

    Agents that keep trying different queries without noticing the result is
    useless will eventually trigger ``repeat`` / ``repeat_by_output`` detection.
    """
    return "No matching results. Please try again."


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
        timeout=300,
        retries=3,
    ),
    oxy.FunctionTool(
        name="buggy_search",
        description="Search a knowledge base. Always returns no results in this demo.",
        func_process=buggy_search,
    ),
    oxy.ReActAgent(
        name="master_agent",
        llm_model="default_llm",
        tools=["buggy_search"],
        prompt="You are a helpful assistant. Use the search tool to find answers.",
        # Enable loop detection in 'block' mode. Switch to 'warn' to let the
        # agent receive a system hint and try to self-correct, or 'disabled' to
        # see the baseline behaviour (will burn through max_react_rounds).
        loop_detection_mode="block",
        loop_fallback_message=(
            "The agent appears to be stuck in a tool-call loop and could not "
            "complete the task. Please rephrase your question."
        ),
        max_react_rounds=10,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="Find the latest research on quantum tunneling.",
            welcome_message="Hi, I'm the loop-detection demo. Ask me anything.",
        )


if __name__ == "__main__":
    asyncio.run(main())
