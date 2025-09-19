import os

from oxygent import MAS, Config, oxy, preset_tools

Config.set_agent_llm_model("default_llm")

os.environ["DEFAULT_LLM_API_KEY"] = "DEFAULT_LLM_API_KEY"
os.environ["DEFAULT_LLM_BASE_URL"] = "DEFAULT_LLM_BASE_URL"
os.environ["DEFAULT_LLM_MODEL_NAME"] = "DEFAULT_LLM_MODEL_NAME"


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
    ),
    preset_tools.time_tools,
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool that can query the time",
        tools=["time_tools"],
    ),
    preset_tools.file_tools,
    oxy.ReActAgent(
        name="file_agent",
        desc="A tool that can operate the file system",
        tools=["file_tools"],
    ),
    preset_tools.math_tools,
    oxy.ReActAgent(
        name="math_agent",
        desc="A tool that can perform mathematical calculations.",
        tools=["math_tools"],
    ),
    preset_tools.http_tools,
    preset_tools.string_tools,
    preset_tools.system_tools,
    preset_tools.shell_tools,
    preset_tools.python_tools,
    preset_tools.baidu_search_tools,
    oxy.ReActAgent(
        name="tool_agent",
        desc="This is a tool library agent, which contains a variety of tools.",
        tools=["http_tools", "string_tools", "system_tools", "shell_tools", "python_tools", "baidu_search_tools"],
    ),
    oxy.ReActAgent(
        is_master=True,
        name="master_agent",
        sub_agents=["time_agent", "file_agent", "math_agent", "tool_agent",],
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="What time is it now? Please save it into time.txt."
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
