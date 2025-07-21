import asyncio
from pydantic import Field

from oxygent import MAS, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.load_from_json("./config.json", env="default")

Config.set_llm_config(
    {
        "temperature": 0.2,
        "max_tokens": 2048,
        "top_p": 0.9,
    }
)

fh = oxy.FunctionHub(name="demo_tools")


@fh.tool(description="Echo what the user says")
async def echo(text: str = Field(description="Text to echo")):
    return f"Echo: {text}"


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
    ),
    fh,
    oxy.ReActAgent(
        name="master_agent",
        is_master=True,
        llm_model="default_llm",
        tools=["echo"],
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="The 30 positions of pi.")


if __name__ == "__main__":
    asyncio.run(main())
