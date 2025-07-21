# examples/ecommerce/app_logistics_service.py

from oxygent import MAS, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_app_name("logistics-service")
Config.set_server_port(8083)

oxy_space = [
    oxy.HttpLLM(
        name="default_name",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    # Logistics Tools
    oxy.StdioMCPClient(
        name="logistics_tools",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "logistics_tools.py"],
        },
    ),
    # Delivery Tools
    oxy.StdioMCPClient(
        name="delivery_tools",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "delivery_tools.py"],
        },
    ),
    # Agent for logistics and delivery
    oxy.ReActAgent(
        name="logistics_agent",
        is_master=True,
        tools=["logistics_tools", "delivery_tools"],
        llm_model="default_name",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
