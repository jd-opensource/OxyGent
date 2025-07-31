"""
依赖 ./05_FunctionHub工具.py 文件，并且需要先启动服务
"""
import os
from oxygent import MAS, oxy, Config, OxyRequest


Config.set_agent_llm_model("default_llm")
Config.set_server_port(8081)   # 在8081端口启动服务

async def note_workflow(oxy_request: OxyRequest):
    query = oxy_request.get_query(master_level=True)

    oxy_response = await oxy_request.call(
        callee="get_current_time",
        arguments={"timezone": "Asia/Shanghai"},
    )

    oxy_response = await oxy_request.call(
        callee="file_agent",
        arguments={
            "query": f"{query}\n现在的时间是：{oxy_response.output}\n格式：[2025年6月18日 10:00]地点 会议\n记录在local_file文件夹的note.txt文件"
        },
    )

    return oxy_response.output

def master_reflexion(response: str, oxy_request: OxyRequest) -> str:
    if not response.startswith("任务已完成！"):
        return "回答时请用“任务已完成！”开头"

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.1},
    ),
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
    oxy.SSEOxyGent(
        name="QA_agent",
        desc="一个可以查询京东知识的助手",
        server_url="http://127.0.0.1:8080",   # 注册远程OxyGent服务
    ),
    oxy.ReActAgent(
        name="file_agent",
        desc="一个可以操作文件的助手",
        tools=["file_tools"],
    ),
    oxy.WorkflowAgent(
        name="note_agent",
        desc="一个记笔记的生活助手",
        sub_agents=["file_agent"],
        tools=["time_tools"],
        func_workflow=note_workflow,
    ),
    oxy.ReActAgent(
        name="master_agent",
        is_master=True,
        sub_agents=["QA_agent", "note_agent"],
        func_reflexion=master_reflexion,
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="京东的211时效是什么？")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
