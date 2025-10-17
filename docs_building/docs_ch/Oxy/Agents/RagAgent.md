检索增强生成，是一种结合信息检索（Retrieval）和文本生成（Generation）的技术。
RAG技术通过实时检索相关文档或信息，并将其作为上下文输入到生成模型中，从而提高生成结果的时效性和准确性。
## Overview
本模块提供了 ChatAgent 类，该类通过管理对话记忆、处理用户查询，并协调语言模型生成回复，从而实现对话式人工智能的交互。
## Quick Start
### Basic Usage
OxyGent支持通过knowledge参数向prompts注入知识。以下将展示一个最简单的RAG示例：
您需要先创建一个retrieval方法：
```python
def retrieval(query):
    # 替换为实际的数据库
    return "\n".join(["knowledge1", "knowledge2", "knowledge3"])
```
然后，需要在update_query中将检索的知识进行注入：
```python
def update_query(oxy_request: OxyRequest):
    current_query = oxy_request.get_query()

    def retrieval(query):
        return "\n".join(["knowledge1", "knowledge2", "knowledge3"])

    oxy_request.arguments["knowledge"] = retrieval(current_query) # Key Method
    return oxy_request
```
## Complete runnable example
以下是可运行的完整代码示例：
```python
import asyncio

from oxygent import MAS, OxyRequest, oxy
from oxygent.utils.env_utils import get_env_var

INSTRUCTION = """
You are a helpful assistant and can use these tools:
${tools_description}

Experience in choosing tools:
${knowledge}

Select the appropriate tool based on the user's question.
If no tool is needed, reply directly.
If answering the user's question requires calling multiple tools, call only one tool at a time. After the user receives the tool result, they will give you feedback on the tool call result.

Important notes:
1. When you have collected enough information to answer the user's question, please respond in the following format:
<think>Your reasoning (if analysis is needed)</think>
Your response content
2. When you find that the user's question lacks certain conditions, you can ask them back. Please respond in the following format:
<think>Your reasoning (if analysis is needed)</think>
Your follow-up question to the user
3. When you need to use a tool, you must respond **only** with the following exact JSON object format, and nothing else:

{
    "think": "Your reasoning (if analysis is needed)",
    "tool_name": "Tool name",
    "arguments": {
        "Parameter name": "Parameter value"
    }
}
"""


def update_query(oxy_request: OxyRequest):
    current_query = oxy_request.get_query()

    def retrieval(query):
        return "\n".join(["knowledge1", "knowledge2", "knowledge3"])

    oxy_request.arguments["knowledge"] = retrieval(current_query)
    return oxy_request


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    oxy.ReActAgent(
        name="master_agent",
        is_master=True,
        llm_model="default_llm",
        timeout=100,
        prompt=INSTRUCTION,
        func_process_input=update_query,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="This is an example for rag. Please modify it according to the specific needs",
        )

if __name__ == "__main__":
    asyncio.run(main())
```
## Configuration Options
### Core Parameters
#### knowledge
1.调用外部注入的检索函数，根据请求内容获取相关知识。
2.将检索到的知识写入 oxy_request.arguments 中的占位符键（knowledge_placeholder），以便后续进行模板渲染或提示词组合。
#### retrieval(str)
根据当前请求执行知识检索（例如，从向量数据库、搜索服务或自托管知识库中检索）。