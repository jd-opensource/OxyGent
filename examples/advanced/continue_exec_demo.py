import asyncio

from oxygent import MAS, Config, OxyRequest, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_agent_llm_model("default_llm")


async def workflow(oxy_request: OxyRequest):
    short_memory = oxy_request.get_short_memory()
    print("--- History record --- :", short_memory)
    master_short_memory = oxy_request.get_short_memory(master_level=True)
    print("--- History record-User layer --- :", master_short_memory)
    print("user query:", oxy_request.get_query(master_level=True))
    await oxy_request.send_message("msg")
    oxy_response = await oxy_request.call(
        callee="time_agent", arguments={"query": "What time is it now?"}
    )
    print("--- Current time --- :", oxy_response.output)
    oxy_response = await oxy_request.call(
        callee="default_llm",
        arguments={
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"},
            ],
            "llm_params": {"temperature": 0.6},
        },
    )
    print(oxy_response.output)
    import re

    numbers = re.findall(r"\d+", oxy_request.get_query())
    if numbers:
        n = numbers[-1]
        oxy_response = await oxy_request.call(callee="pi", arguments={"prec": n})
        return f"Save {n} positions: {oxy_response.output}"
    else:
        return "Save 2 positions: 3.14, or you could ask me to save how many positions you want."


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
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
        is_master=True,
    ),
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool for time query.",
        tools=["time"],
    ),
    oxy.ReActAgent(
        name="file_agent",
        desc="A tool for file operation.",
        tools=["filesystem"],
    ),
    oxy.WorkflowAgent(
        name="math_agent",
        desc="A tool for pi query.",
        sub_agents=["time_agent"],
        tools=["my_tools"],
        func_workflow=workflow,
        is_retain_master_short_memory=True,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        # first
        payload = {
            "query": "Get what time it is in America/New_York and save in `log.txt` under `./local_file`",
        }
        # second
        payload = {
            "query": "Get what time it is in America/New_York and save in `log.txt` under `./local_file`",  # TODO: get from trace id
            "from_trace_id": "",
            "reference_trace_id": "CVu84yL8jbk3UwT6",  # TODO: get from node id
            "restart_node_id": "gn7YBoKeTxr439ps",
            "restart_node_output": """{
                "timezone": "America/New_York",
                "datetime": "2024-07-21T05:32:43-04:00",
                "is_dst": true
            }""",
        }
        oxy_response = await mas.chat_with_agent(payload=payload)
        from_trace_id = oxy_response.oxy_request.current_trace_id
        print("LLM: ", oxy_response.output, from_trace_id)


async def test():
    async with MAS(oxy_space=oxy_space) as mas:
        out = await mas.chat_with_agent(
            payload={
                "query": "Get what time it is in America/New_York and save in `log.txt` under `./local_file`",
                "from_trace_id": "",
                "reference_trace_id": "ueCFLfMQe7BByS7d",
                "restart_node_id": "mixmmY6vh4aMDLbP",
                "restart_node_output": """{
                "timezone": "Asia/Shanghai",
                "datetime": "2024-07-06T20:03:02+08:00",
                "is_dst": false
            }""",
            }
        )
        print(out.output)


if __name__ == "__main__":
    asyncio.run(main())
