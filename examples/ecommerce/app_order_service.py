# examples/ecommerce/app_order_service.py

from oxygent import MAS, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_app_name("order-service")
Config.set_server_port(8081)


oxy_space = [
    oxy.HttpLLM(
        name="default_name",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    # order management tools
    oxy.StdioMCPClient(
        name="order_tools",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "order_tools.py"],
        },
    ),
    # payment service agent
    oxy.SSEOxyGent(
        name="payment_service",
        desc="Payment service intelligent twin, professional processing of payment-related business: support to query payment status and payment details according to the order number, as well as provide a variety of payment methods query and payment channel information consulting services",
        server_url="http://127.0.0.1:8082",
    ),
    # order management agent
    oxy.ReActAgent(
        name="order_agent",
        is_master=True,
        tools=["order_tools"],
        sub_agents=["payment_service"],
        llm_model="default_name",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
