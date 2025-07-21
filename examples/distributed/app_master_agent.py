import json

from oxygent import MAS, oxy
from oxygent.utils.env_utils import get_env_var

with open("config.json", "r") as f:
    config = json.load(f)

oxy_space = [
    oxy.HttpLLM(
        name="default_name",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    oxy.StdioMCPClient(
        name="filesystem",
        params={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "./local_file"],
        },
    ),
    oxy.ReActAgent(
        name="master_agent",
        sub_agents=["file_agent", "math_agent"],
        is_master=True,
        llm_model="default_name",
    ),
    oxy.ReActAgent(
        name="file_agent",
        desc="A tool for querying local files",
        tools=["filesystem"],
        llm_model="default_name",
    ),
    oxy.SSEOxyGent(
        name="math_agent",
        desc="A tool for mathematical calculations",
        server_url="http://127.0.0.1:8081",
        is_share_call_stack=False,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="The first 30 positions of pi")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
