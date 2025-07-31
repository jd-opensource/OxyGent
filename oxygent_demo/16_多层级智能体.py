import os
from oxygent import MAS, oxy, Config
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


note_prompt = """
你是一个帮助用户记备忘录的助手，格式按照：
[2025年6月18日 10:00]地点 会议
[2025年11月11日 晚上]值班
你应该先获取时间使用上海时区，然后记录在local_file文件夹的note.txt文件，没有该文件时请创建。

你可以使用这些工具：
${tools_description}

根据用户的问题选择合适的工具。
如果不需要工具，直接回复。
如果回答用户的问题需要调用多次工具，每次只调用一个工具，用户收到工具后，会给你反馈工具调用结果。

重要提示：
1. 当你收集到的信息足够回答用户问题时，请按以下格式回答：
<think>你的思考（如果需要分析）</think>
你的回答内容
2. 当你发现用户问题缺乏条件时，你可以反问用户，请按以下格式回答：
<think>你的思考（如果需要分析）</think>
你反问用户的问题
3. 当你需要使用一个工具时，你必须只响应下面确切的JSON对象格式，别无其他：
```json
{
    "think": "你的思考（如果需要分析）",
    "tool_name": "工具名称",
    "arguments": {
        "参数名": "参数值"
    }
}
```

在收到工具的响应后：
1. 将原始数据转换为自然的会话响应
2. 回答要简洁但内容丰富
3. 关注最相关的信息
4. 从用户的问题中使用适当的上下文
5. 避免简单地重复原始数据

请仅使用上面明确定义的工具。
"""


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
    oxy.ReActAgent(   # 2级智能体
        name="QA_agent",
        desc="一个可以查询京东知识的助手",
        tools=["jd_docs_tools"],
    ),
    oxy.ReActAgent(   # 3级智能体
        name="time_agent",
        desc="一个可以查询时间的助手",
        tools=["time_tools"],
    ),
    oxy.ReActAgent(   # 3级智能体
        name="file_agent",
        desc="一个可以操作文件的助手",
        tools=["file_tools"],
    ),
    oxy.ReActAgent(   # 2级智能体
        name="note_agent",
        desc="一个记笔记的生活助手",
        prompt=note_prompt,
        sub_agents=["time_agent", "file_agent"],
    ),
    oxy.ReActAgent(   # 1级智能体
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
