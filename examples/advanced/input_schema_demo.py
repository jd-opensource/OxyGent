import asyncio

from oxygent import MAS, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_agent_llm_model("default_llm")
Config.load_from_json("./config.json")
Config.set_agent_input_schema(
    {
        "properties": {
            "query": {"description": "Query question"},
            "path": {"description": "File path to save the result"},
        },
        "required": ["query"],
    }
)


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY", expected_type=str),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL", expected_type=str),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME", expected_type=str),
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
        sub_agents=["file_agent"],
        timeout=100,
        is_master=True,
        llm_model="default_llm",
    ),
    oxy.ReActAgent(
        name="file_agent",
        desc="A tool for file operation.",
        tools=["filesystem"],
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query='Please save "OxyGent is all you need" to the file log.txt under the local_file folder.'
        )


if __name__ == "__main__":
    asyncio.run(main())
