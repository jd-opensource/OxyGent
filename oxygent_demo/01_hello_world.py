import os
from oxygent import MAS, oxy

oxy_space = [
    oxy.HttpLLM(   # 注册大模型
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
    ),
    oxy.ChatAgent(   # 注册问答智能体
        name="QA_agent",
        llm_model="default_llm",   # 装配大模型
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="你好")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
