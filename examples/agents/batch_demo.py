import asyncio

from pydantic import Field

from oxygent import MAS, Config, OxyRequest, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_agent_llm_model("default_llm")


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
        oxy_response = await oxy_request.call(callee="pi", arguments={"prec": n})
        return f"Save {n} positions: {oxy_response.output}"
    else:
        return "Save 2 positions: 3.14, or you could ask me to save how many positions you want."


fh = oxy.FunctionHub(name="joke_tools")


@fh.tool(description="a tool for telling jokes")
async def joke_tool(joke_type: str = Field(description="The type of the jokes")):
    import random

    jokes = [
        "Teacher: Can you use the word 'because' in a sentence? \n Student: I didn't do my homework because… because I didn't do my homework.",
        "Patient: Doctor, I feel like a pair of curtains.\nDoctor: Pull yourself together!",
        "How many software engineers does it take to change a light bulb?\nNone. That's a hardware problem.",
    ]
    print("The type of the jokes", joke_type)
    return random.choice(jokes)


def update_query(oxy_request: OxyRequest):
    print(oxy_request.shared_data)
    user_query = oxy_request.get_query(master_level=True)
    current_query = oxy_request.get_query()
    print(user_query + "\n" + current_query)
    oxy_request.arguments["who"] = oxy_request.callee
    return oxy_request


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={
            "temperature": 0.7,
            "max_tokens": 512,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        semaphore=200,
    ),
    fh,
    oxy.StdioMCPClient(
        name="time",
        params={
            "command": "uvx",
            "args": ["mcp-server-time", "--local-timezone=Asia/Shanghai"],
        },
    ),
    oxy.StdioMCPClient(
        name="filesystem",
        params={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "./local_file"],
        },
    ),
    oxy.StdioMCPClient(
        name="my_tools",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "my_tools.py"],
        },
    ),
    oxy.ReActAgent(
        name="master_agent",
        sub_agents=["time_agent", "file_agent", "math_agent"],
        tools=["joke_tool", "my_tools"],
        is_master=True,
        llm_model="default_llm",
        semaphore=200,
        timeout=100,
    ),
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool for time query.",
        tools=["time"],
        llm_model="default_llm",
        func_process_input=update_query,
        trust_mode=True,
        timeout=10,
    ),
    oxy.ReActAgent(
        name="file_agent",
        desc="A tool for file operation.",
        tools=["filesystem"],
        llm_model="default_llm",
    ),
    oxy.WorkflowAgent(
        name="math_agent",
        desc="A tool for pi query",
        sub_agents=["time_agent"],
        tools=["my_tools"],
        func_workflow=workflow,
        llm_model="default_llm",
        is_retain_master_short_memory=True,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        outs = await mas.start_batch_processing(["Hello!"] * 10, return_trace_id=True)
        print(outs)


if __name__ == "__main__":
    asyncio.run(main())
