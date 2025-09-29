import asyncio
import os

from oxygent import MAS, oxy

oxy_space = [
    oxy.HttpLLM(
        name="default_vlm",
        api_key=os.getenv("DEFAULT_VLM_API_KEY"),
        base_url=os.getenv("DEFAULT_VLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_VLM_MODEL_NAME"),
        is_multimodal_supported=True,
        is_convert_url_to_base64=True,
    ),
    oxy.ChatAgent(
        name="vision_agent",
        llm_model="default_vlm",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="What is this?")


if __name__ == "__main__":
    asyncio.run(main())
