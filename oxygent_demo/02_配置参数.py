import os
from oxygent import MAS, oxy

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.1},   # 配置大模型参数
    ),
    oxy.ChatAgent(
        name="QA_agent",
        llm_model="default_llm",
        prompt="你是一个乐于助人的助手！"   # 配置智能体参数
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="你好")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
