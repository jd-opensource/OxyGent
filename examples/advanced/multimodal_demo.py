import asyncio

from oxygent import MAS, Config, OxyRequest, OxyResponse, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_agent_llm_model("default_vlm")


async def master_workflow(oxy_request: OxyRequest) -> OxyResponse:
    generate_agent_oxy_response = await oxy_request.call(
        callee="generate_agent",
        arguments={
            "query": oxy_request.get_query(),
            "attachments": oxy_request.arguments.get("attachments", []),
            "llm_params": {"temperature": 0.6},
        },
    )
    discriminate_agent_oxy_response = await oxy_request.call(
        callee="discriminate_agent",
        arguments={
            "query": str(generate_agent_oxy_response.output),
            "attachments": oxy_request.arguments.get("attachments", []),
        },
    )
    return f"generate_agent output output: {generate_agent_oxy_response.output} \n discriminate_agent output: {discriminate_agent_oxy_response.output}"


# Init oxy_space
oxy_space = [
    oxy.HttpLLM(
        name="default_vlm",
        api_key=get_env_var("DEFAULT_VLM_API_KEY"),
        base_url=get_env_var("DEFAULT_VLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_VLM_MODEL_NAME"),
        llm_params={"temperature": 0.6, "max_tokens": 2048},
        max_pixels=10000000,
        is_multimodal_supported=True,
        is_convert_url_to_base64=True,
        semaphore=4,
    ),
    oxy.ChatAgent(
        name="generate_agent",
        prompt="You are a helpful assistant. Please describe the content of the image in detail.",
    ),
    oxy.ChatAgent(
        name="discriminate_agent",
        prompt="Please determine whether the following text is a description of the content of the image. If it is, please output 'True', otherwise output 'False'.",
    ),
    oxy.Workflow(
        name="master_agent",
        is_master=True,
        permitted_tool_name_list=["generate_agent", "discriminate_agent"],
        func_workflow=master_workflow,
    ),
]

"""
oxy.ReActAgent output example: 
return OxyOutput(
    result="What is it in the picture? ",
    attachments=["./cache_dir/uploads/20250705122650_20250626090420425.png"],
)
"""


async def main():
    # Multimoding
    async with MAS(oxy_space=oxy_space) as mas:
        """Single-round dialogue"""
        payload = {
            "query": "What is it in the picture?",
            "attachments": [get_env_var("DEFAULT_IMAGE_URL")],
        }
        oxy_response = await mas.chat_with_agent(payload=payload)
        print("LLM: ", oxy_response.output)

        """Multi-round dialogue
        from_trace_id = ""
        while True: 
            payload = {
                "query": "What is it in the picture?",
                "attachments": [get_env_var("DEFAULT_IMAGE_URL")],
                "from_trace_id": from_trace_id,
            }
            oxy_response = await mas.chat_with_agent(payload=payload)
            from_trace_id = oxy_response.oxy_request.current_trace_id
            print("LLM: ", oxy_response.output)
        """


if __name__ == "__main__":
    asyncio.run(main())
