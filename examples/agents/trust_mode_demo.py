import asyncio
from oxygent import MAS, oxy
from oxygent.utils.env_utils import get_env_var

oxy_space = [
    # LLM configuration
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    # time tool
    oxy.StdioMCPClient(
        name="time",
        params={
            "command": "uvx",
            "args": ["mcp-server-time", "--local-timezone=Asia/Shanghai"],
        },
    ),
    # normal mode ReActAgent
    oxy.ReActAgent(
        name="normal_agent",
        desc="a time query agent with trust mode disabled",
        tools=["time"],
        llm_model="default_llm",
        trust_mode=False,  # disable trust mode
    ),
    # trust mode ReActAgent
    oxy.ReActAgent(
        name="trust_agent",
        desc="a time query agent with trust mode enabled",
        tools=["time"],
        llm_model="default_llm",
        trust_mode=True,  # enable trust mode
        is_master=True,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        query = "What is the current time"

        print("=== normal mode test ===")
        normal_result = await mas.call("normal_agent", {"query": query})
        print(f"normal mode output: {normal_result}")

        print("\n=== trust mode test ===")
        trust_result = await mas.call("trust_agent", {"query": query})
        print(f"trust mode output: {trust_result}")


if __name__ == "__main__":
    asyncio.run(main())
