import os
from oxygent import MAS, oxy, Config, OxyRequest
from pydantic import Field


Config.set_agent_llm_model("default_llm")


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


# 自定义workflow函数
async def note_workflow(oxy_request: OxyRequest):
    query = oxy_request.get_query()

    # 直接调用time_agent
    oxy_response = await oxy_request.call(
        callee="time_agent",
        arguments={"query": "现在几点"},
    )

    # 直接调用file_agent
    oxy_response = await oxy_request.call(
        callee="file_agent",
        arguments={
            "query": f"{query}\n现在的时间是：{oxy_response.output}\n格式：[2025年6月18日 10:00]地点 会议\n记录在local_file文件夹的note.txt文件"
        },
    )

    return oxy_response.output



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
        desc="一个可以查询京东知识的助手",
        tools=["jd_docs_tools"],
    ),
    oxy.ReActAgent(
        name="time_agent",
        desc="一个可以查询时间的助手",
        tools=["time_tools"],
    ),
    oxy.ReActAgent(
        name="file_agent",
        desc="一个可以操作文件的助手",
        tools=["file_tools"],
    ),
    oxy.WorkflowAgent(
        name="note_agent",
        desc="一个记笔记的生活助手",
        sub_agents=["time_agent", "file_agent"],
        func_workflow=note_workflow,   # 注册workflow函数
    ),
    oxy.ReActAgent(
        name="master_agent",
        is_master=True,
        sub_agents=["QA_agent", "note_agent"],
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="帮我记个备忘录，下午3点在618会议室开会")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
