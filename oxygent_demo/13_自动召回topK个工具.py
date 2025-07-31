import os
from oxygent import MAS, oxy, Config
from pydantic import Field


Config.load_from_json("./config.json", env="dev")   # 指定使用 dev 环境：配置Vearch向量库和Embedding模型


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
    ),
    jd_docs_fh,
    oxy.StdioMCPClient(
        name="time_tools",
        params={
            "command": "uvx",
            "args": ["mcp-server-time", "--local-timezone=Asia/Shanghai"],
        },
    ),
    oxy.StdioMCPClient(
        name="file_tools",
        params={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "./local_file"],
        },
    ),
    oxy.ReActAgent(
        name="QA_agent",
        llm_model="default_llm",
        tools=["jd_docs_tools", "time_tools", "file_tools"],
        top_k_tools=3,   # 仅召回 top 3 个工具
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="现在几点")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
