# examples/ecommerce/app_product_service.py

from oxygent import MAS, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_app_name("product-service")
Config.set_server_port(8080)

oxy_space = [
    oxy.HttpLLM(
        name="default_name",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    # Database tool
    oxy.StdioMCPClient(
        name="product_db",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "product_tools.py"],
        },
    ),
    # Inventory management tool
    oxy.StdioMCPClient(
        name="inventory_tools",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "inventory_tools.py"],
        },
    ),
    # Product agent
    oxy.ReActAgent(
        name="product_agent",
        is_master=True,
        tools=["product_db", "inventory_tools"],
        llm_model="default_name",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
