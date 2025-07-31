import os
from oxygent import MAS, oxy
from pydantic import Field


jd_docs_fh = oxy.FunctionHub(name="jd_docs_tools")

@jd_docs_fh.tool(description="一个可以召回京东相关知识的工具")
def retrieval(query: str = Field(description="什么方面的知识")) -> str:
    """以下用字符匹配模拟，而生产环境中，通常根据query从知识库中召回topK条相关语料，可以增加多路召回逻辑"""
    knowledage_dict = {
        "211时效": "**京东211时效**：当日上午 11:00 前提交的现货订单(部分城市为上午 10:00 点前），当日送达；当日 23:00 前提交的现货订单，次日 15:00 前送达。(注：先货订单以提交时间点开始计算，先款订单以支付完成时间点计算)",
        "使命": "京东的使命是 “技术为本，让生活更美好”。",
        "愿景": "京东的愿景是成为全球最值得信赖的企业。",
        "价值观": "京东核心价值观是：客户为先、创新、拼搏、担当、感恩、诚信。",
    }
    return "\n\n".join([v for k, v in knowledage_dict.items() if k in query])


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.1},
        semaphore=4,   # 限制并发数量
    ),
    jd_docs_fh,
    oxy.ReActAgent(
        name="QA_agent",
        llm_model="default_llm",
        tools=["jd_docs_tools"],
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        querys = [
            "京东的211时效是什么？",
            "京东的35711是什么",
            "京东的三毛五理论是什么",
            "京东的价值观是什么",
            "京东的使命是什么",
            "京东的战略三问是什么",
            "京东的愿景是什么",
        ]
        answers = await mas.start_batch_processing(querys)
        for query, answer in zip(querys, answers):
            print("-" * 100)
            print("Q:", query)
            print("A:", answer)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
