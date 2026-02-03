import asyncio
import os

# 【新增】引入 OxyRequest 用于工作流函数定义
from oxygent import MAS, Config, oxy, preset_tools, OxyRequest

Config.set_agent_llm_model("default_llm")

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"stream": True},
    ),
    preset_tools.video_understanding_tools,
    oxy.ReActAgent(
        name="video_understanding_agent",
        desc="A tool can understand the video.",
        tools=["video_understanding_tools"],
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="hello")

if __name__ == "__main__":
    asyncio.run(main())