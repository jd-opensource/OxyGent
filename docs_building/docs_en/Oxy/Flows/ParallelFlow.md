# ParallelFlow

## Overview

> [!TIP]
> `ParallelFlow` is a more fundamental component for parallel execution, suitable for scenarios that require simple aggregation of outputs from multiple tools. If intelligent summarization is needed, it is recommended to use `ParallelAgent`.

OxyGent provides a preset `ParallelFlow` class for managing parallel execution flows. `ParallelFlow` allows multiple tools or agents to run concurrently and consolidates their outputs into a single unified response.

Use `ParallelFlow` when the tools or agents involved have no interdependencies, as it enables parallel execution of tasks and reduces overall processing time.

At its core, `ParallelFlow` dispatches the same request to all available tools or agents simultaneously, executes these calls in parallel using `asyncio.gather`, and aggregates all results into a single response.

## Full Example: Parallel Revenue Fetching

Imagine fetching revenue data for multiple companies simultaneously:

- **Revenue Agent 1**: A tool that fetches revenue for Company A
- **Revenue Agent 2**: A tool that fetches revenue for Company B
- **Revenue Agent 3**: A tool that fetches revenue for Company C

These revenue-fetching tasks are independent. Using a ParallelFlow allows them to run concurrently, significantly reducing total wait time compared to running sequentially. After all agents finish, the results are collected and sorted from highest to lowest revenue.

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
    print(f"Random pause for {sleep_time} seconds...")
    await asyncio.sleep(sleep_time)
    return revenue

@fh.tool(description="a tool for get revenue of companyA")
async def get_j_revenue():
    return f'The revenue of companyA is {await get_random_revenue()}'

@fh.tool(description="a tool for get revenue of companyB")
async def get_a_revenue():
    return f'The revenue of companyB is {await get_random_revenue()}'

@fh.tool(description="a tool for get revenue of companyC")
async def get_p_revenue():
    return f'The revenue of companyC is {await get_random_revenue()}'

def update_query(oxy_request: OxyRequest) -> OxyRequest:
    print(oxy_request.shared_data)
    user_query = oxy_request.get_query(master_level=True)
    current_query = oxy_request.get_query()
    print(user_query + "\n" + current_query)
    oxy_request.arguments["who"] = oxy_request.callee
    return oxy_request

def format_output(oxy_response: OxyResponse) -> OxyResponse:
    oxy_response.output = "Answer: " + oxy_response.output
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
        desc="Fetch revenue data for three companies in parallel",
        permitted_tool_name_list=[
            "get_j_revenue",
            "get_a_revenue",
            "get_p_revenue",
        ]
    ),
    oxy.ReActAgent(
        name="master_agent",
        sub_agents=["revenue_parallel_flow"],
        additional_prompt="You are a data analysis assistant responsible for analyzing and sorting company revenue data.",
        is_master=True,
        func_format_output=format_output,
        timeout=100,
        llm_model="default_llm",
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="Please fetch revenue data for companies A, B, and C, and sort them from highest to lowest revenue",
            welcome_message="Hi, I'm OxyGent. How can I assist you?",
        )

if __name__ == "__main__":
    asyncio.run(main())
```