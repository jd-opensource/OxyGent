"""Demo for using OxyGent with multiple LLMs and an agent."""

import asyncio

from oxygent import MAS, oxy
from oxygent.utils.env_utils import get_env_var


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
    ),
    oxy.StdioMCPClient(
        name="my_tools",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "path_tools.py"],
        },
    ),
    oxy.ChatAgent(
        name="planner",
        llm_model="default_llm",
        prompt=(
            "You are a planning agent.  "
            "Output **only** a JSON object that matches this schema:\n"
            '{"steps": ["step 1", "step 2", ...]}\n'
        ),
    ),
    oxy.ReActAgent(
        name="executor",
        llm_model="default_llm",
        tools=["my_tools"],
    ),
    oxy.PlanAndSolve(
        name="analyser",
        llm_model="default_llm",
        planner_agent_name="planner",
        executor_agent_name="executor",
        enable_replanner=False,
    ),
    oxy.ReActAgent(
        name="master",
        llm_model="default_llm",
        prompt="""
            You are the orchestration agent.

            **Rules**
            1. If the user message is exactly a greeting (hi / hello / 你好), reply normally.
            2. Otherwise, you MUST call the tool `analyser` with the full user query.

            **Tool call format**
            ```json
            {"tool_name": "analyser", "arguments": {"query": "<user_query>"} }

            Do NOT wrap the JSON in triple back-ticks or double braces.
            Return nothing else.

            for example:
                User: hi
                Assistant: Hello!

                User: Do X and Y …
                Assistant:
                {"tool_name": "analyser", "arguments": {"query": "Do X and Y …"}}
        """.strip(),
        sub_agents=["analyser"],
        is_master=True,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        # "hello"
        # "Please help me find a path from A to B, the cost is less than 5, the time is less than 3"
        await mas.start_web_service(
            first_query="Please help me find a path from A to B, the cost is less than 5, the time is less than 3"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
