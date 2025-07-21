import asyncio

from oxygent import MAS, OxyRequest, oxy
from oxygent.utils.env_utils import get_env_var

INSTRUCTION = """
You are a helpful assistant and can use these tools:
${tools_description}

Experience in choosing tools:
${knowledge}

Select the appropriate tool based on the user's question.
If no tool is needed, reply directly.
If answering the user's question requires calling multiple tools, call only one tool at a time. After the user receives the tool result, they will give you feedback on the tool call result.

Important notes:
1. When you have collected enough information to answer the user's question, please respond in the following format:
<think>Your reasoning (if analysis is needed)</think>
Your response content
2. When you find that the user's question lacks certain conditions, you can ask them back. Please respond in the following format:
<think>Your reasoning (if analysis is needed)</think>
Your follow-up question to the user
3. When you need to use a tool, you must respond **only** with the following exact JSON object format, and nothing else:
```json
{
    "think": "Your reasoning (if analysis is needed)",
    "tool_name": "Tool name",
    "arguments": {
        "Parameter name": "Parameter value"
    }
}
"""


def update_query(oxy_request: OxyRequest):
    current_query = oxy_request.get_query()

    def retrieval(query):
        return "\n".join(["knowledge1", "knowledge2", "knowledge3"])

    oxy_request.arguments["knowledge"] = retrieval(current_query)
    return oxy_request


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    oxy.ReActAgent(
        name="master_agent",
        is_master=True,
        llm_model="default_llm",
        timeout=100,
        prompt=INSTRUCTION,
        func_process_input=update_query,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="Get what time it is and save in `log.txt` under `/local_file`"
        )


async def test():
    async with MAS(oxy_space=oxy_space) as mas:
        out = await mas.chat_with_agent(
            payload={
                "query": "Get what time it is and save in `log.txt` under `/local_file`"
            }
        )
        print(out)


if __name__ == "__main__":
    asyncio.run(main())
