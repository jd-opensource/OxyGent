import os
from oxygent import MAS, Config, oxy
from oxygent.preset_tools.request_tools import request_tools

Config.set_agent_llm_model("default_llm")

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    request_tools,
    oxy.ReActAgent(
        name="request_agent",
        desc="A tool that can access request context and demonstrate oxy_request functionality",
        tools=["advanced_tool"],
    ),
    oxy.ReActAgent(
        is_master=True,
        name="master_agent",
        sub_agents=["request_agent"],
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        print("=== Testing request_tools in CLI mode ===")
        await mas.start_cli_mode(
            first_query="Please use the advanced_tool to show me the trace_id and any shared data available."
        )


async def test_direct_call():
    async with MAS(oxy_space=oxy_space) as mas:
        print("=== Direct call test ===")

        response = await mas.chat_with_agent(
            {
                "query": "Please use the advanced_tool in request_agent to demonstrate accessing request context. Show me the trace_id and shared_data if they are returned by the 'advanced_tool'.",
                "shared_data": {"test_key": "test_value", "user_info": "demo_user"},
            }
        )

        print(f"Response: {response.output}")
        print(f"Trace ID: {response.oxy_request.current_trace_id}")

        response2 = await mas.chat_with_agent(
            {
                "query": "Call the advanced_tool in request_agent again and show me the trace_id and shared_data if they are returned by the 'advanced_tool'.",
                "from_trace_id": response.oxy_request.current_trace_id,
                "shared_data": {"conversation_step": "second_call"},
            }
        )

        print(f"Second Response: {response2.output}")
        print(f"Second Trace ID: {response2.oxy_request.current_trace_id}")


if __name__ == "__main__":
    import asyncio

    test_mode = "direct"

    if test_mode == "direct":
        asyncio.run(test_direct_call())
    elif test_mode == "cli":
        asyncio.run(main())
    elif test_mode == "web":

        async def web_main():
            async with MAS(oxy_space=oxy_space) as mas:
                await mas.start_web_service(
                    first_query="Please use the advanced_tool to show me the trace_id and any shared data available."
                )

        asyncio.run(web_main())
