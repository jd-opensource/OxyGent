# ParallelFlow

## 介绍

> [!TIP]
> `ParallelFlow` 是更基础的并行执行组件，适合需要简单聚合多个工具输出的场景。如果需要智能总结，建议使用 `ParallelAgent`。

OxyGent 提供了预设的 `ParallelFlow` 类用于实现并行流。`ParallelFlow` 类可以同时执行多个工具或智能体，并将它们的结果聚合成统一的响应。

当您使用的多个工具或者智能体之间不存在依赖关系时，可以考虑使用 `ParallelFlow` 并行执行这些任务，以减少整体的处理时长。

`ParallelFlow` 的核心功能是将同一个请求同时分发给所有可用的工具或智能体，然后使用 `asyncio.gather` 并行执行这些工具调用，最后将所有输出聚合到单个响应中。

## 完整的可运行样例

想象一下同时获取多家公司的营收数据：

- **营收智能体 1**：一个获取 公司A 营收数据的工具
- **营收智能体 2**：一个获取 公司B 营收数据的工具
- **营收智能体 3**：一个获取 公司C 营收数据的工具

这些营收获取任务是相互独立的。使用 `ParallelFlow` 可以让它们并发运行，与顺序执行相比能显著减少总等待时间。所有任务完成后，结果会被汇总，并按照营收从高到低排序。

```python
import asyncio
import os

from pydantic import Field

from oxygent import MAS, Config, OxyRequest, OxyResponse, oxy
from oxygent.prompts import INTENTION_PROMPT

Config.set_agent_llm_model("default_llm")

fh = oxy.FunctionHub(name="revenue_tools")

async def get_random_revenue():
    import random
    revenue = random.randint(1000000, 100000000)
    sleep_time = random.randint(1, 5)
    print(f"随机暂停 {sleep_time} 秒...")
    await asyncio.sleep(sleep_time)
    return revenue

@fh.tool(description="获取公司A营收的工具")
async def get_j_revenue():
    return f'公司A的营收为 {await get_random_revenue()}'

@fh.tool(description="获取公司B营收的工具")
async def get_a_revenue():
    return f'公司B的营收为 {await get_random_revenue()}'

@fh.tool(description="获取公司C营收的工具")
async def get_p_revenue():
    return f'公司C的营收为 {await get_random_revenue()}'


def update_query(oxy_request: OxyRequest) -> OxyRequest:
    print(oxy_request.shared_data)
    user_query = oxy_request.get_query(master_level=True)
    current_query = oxy_request.get_query()
    print(user_query + "\n" + current_query)
    oxy_request.arguments["who"] = oxy_request.callee
    return oxy_request


def format_output(oxy_response: OxyResponse) -> OxyResponse:
    oxy_response.output = "答案: " + oxy_response.output
    return oxy_response


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    oxy.ChatAgent(name="intent_agent", prompt=INTENTION_PROMPT),
    fh,
    oxy.flows.ParallelFlow(
        name="revenue_parallel_flow",
        desc="并行获取三家公司的营收数据",
        permitted_tool_name_list=[
            "get_j_revenue",
            "get_a_revenue",
            "get_p_revenue",
        ]
    ),
    oxy.ReActAgent(
        name="master_agent",
        sub_agents=["revenue_parallel_flow"],
        additional_prompt="你是一个数据分析助手，负责分析和排序公司营收数据。",
        is_master=True,
        func_format_output=format_output,
        timeout=100,
        llm_model="default_llm",
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="请获取公司A、B、C的营收数据，并按营收从高到低排序",
            welcome_message="您好，我是 OxyGent。我能为您做些什么？",
        )


if __name__ == "__main__":
    asyncio.run(main())
```