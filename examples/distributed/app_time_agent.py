from oxygent import MAS, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_app_name("app-time")
Config.set_server_port(8082)

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
        name="time",
        params={
            "command": "uvx",
            "args": ["mcp-server-time", "--local-timezone=Asia/Shanghai"],
        },
    ),
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool for time query",
        is_master=True,
        tools=["time"],
        llm_model="default_name",
        timeout=10,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="What time is it now?")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
