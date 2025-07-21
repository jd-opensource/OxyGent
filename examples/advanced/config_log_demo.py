import asyncio
from pydantic import Field

from oxygent import MAS, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.load_from_json("./config.json", env="default")

Config.set_log_config(
    {
        "path": "./cache_dir/demo.log",
        "level_root": "DEBUG",
        "level_terminal": "DEBUG",
        "level_file": "DEBUG",
        "color_is_on_background": True,
        "is_bright": True,
        "only_message_color": False,
        "color_tool_call": "MAGENTA",
        "color_observation": "GREEN",
        "is_detailed_tool_call": True,
        "is_detailed_observation": True,
    }
)

fh = oxy.FunctionHub(name="demo_tools")


@fh.tool(description="Return the length of the given text")
async def strlen(text: str = Field(description="Any text")) -> int:
    return len(text)


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
        tools=["strlen"],
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="How many chars in 'OxyGent'?")


if __name__ == "__main__":
    asyncio.run(main())
