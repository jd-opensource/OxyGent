import json

from oxygent import MAS, Config, OxyRequest, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_app_name("app-math")
Config.set_server_port(8081)

with open("config.json", "r") as f:
    config = json.load(f)


async def workflow(oxy_request: OxyRequest):
    short_memory = oxy_request.get_short_memory()
    print("--- History record --- :", short_memory)
    master_short_memory = oxy_request.get_short_memory(master_level=True)
    print("--- History record: User Layer --- :", master_short_memory)
    print("user query:", oxy_request.get_query(master_level=True))
    oxy_response = await oxy_request.call(
        callee="time_agent", arguments={"query": "What time is it now?"}
    )
    print("--- Current time --- :", oxy_response.output)
    import re

    numbers = re.findall(r"\d+", oxy_request.get_query())
    if numbers:
        n = numbers[-1]
        oxy_response = await oxy_request.call(callee="calc_pi", arguments={"prec": n})
        return f"Save {n} positions: {oxy_response.output}"
    else:
        return "Save 2 positions: 3.14, or you could ask me to save how many positions you want."


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
        name="my_tools",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "my_tools.py"],
        },
    ),
    oxy.SSEOxyGent(
        name="time_agent",
        desc="An tool for time query",
        server_url="http://127.0.0.1:8082",
    ),
    oxy.WorkflowAgent(
        name="math_agent",
        desc="An tool for pi query",
        is_master=True,
        sub_agents=["time_agent"],
        tools=["my_tools"],
        func_workflow=workflow,
        llm_model="default_name",
        is_retain_master_short_memory=True,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="The 30 positions of pi")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
