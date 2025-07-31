"""
依赖 ./mcp_servers/jd_docs_sse.py 文件，并且需要先启动 SSE MCP 服务器
"""
import os
from oxygent import MAS, oxy

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.1},
    ),
    oxy.SSEMCPClient(   # 注册SSEMCP工具
        name="jd_docs_tools",
        sse_url="http://127.0.0.1:9000/sse"
    ),
    oxy.ReActAgent(
        name="QA_agent",
        llm_model="default_llm",
        tools=["jd_docs_tools"],   # 给Agent装配工具
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="京东的211时效是什么？")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
