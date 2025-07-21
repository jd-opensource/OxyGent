import asyncio
import os
import sys
from pydantic import Field

from oxygent import MAS, OxyRequest, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.load_from_json("./config.json", env="default")

Config.set_message_config(
    {
        "is_send_tool_call": False,
        "is_send_observation": False,
        "is_send_think": False,
        "is_send_answer": True,
    }
)

current_dir = os.path.dirname(os.path.abspath(__file__))

parent_dir = os.path.dirname(os.path.dirname(current_dir))

# Add current directory and 2 layers of parent directory to path
sys.path.append(parent_dir)


async def workflow(oxy_request: OxyRequest):
    short_memory = oxy_request.get_short_memory()
    print("--- History record --- ：", short_memory)
    master_short_memory = oxy_request.get_short_memory(master_level=True)
    print("--- History record: User Layer --- ：", master_short_memory)
    print("user query:", oxy_request.get_query(master_level=True))
    oxy_response = await oxy_request.call(
        callee="time_agent", arguments={"query": "What time is it now?"}
    )
    print("--- Current time --- ：", oxy_response.output)
    import re

    numbers = re.findall(r"\d+", oxy_request.get_query())
    if numbers:
        n = int(numbers[-1])
        oxy_response = await oxy_request.call(callee="calc_pi", arguments={"prec": n})
        return f"Save {n} positions: {oxy_response.output}"
    else:
        return "Save 2 positions: 3.14, or you could ask me to save how many positions you want."


math_fh = oxy.FunctionHub(name="math_tools")


@math_fh.tool(description="Index tool")
def power(
    n: int = Field(description="base"), m: int = Field(description="index", default=2)
) -> int:
    import math

    return math.pow(n, m)


@math_fh.tool(description="Pi calculating tool")
def calc_pi(prec: int = Field(description="cal pi with assigned positions")) -> float:
    import math
    from decimal import Decimal, getcontext

    getcontext().prec = prec
    x = 0
    for k in range(int(prec / 8) + 1):
        a = 2 * Decimal.sqrt(Decimal(2)) / 9801
        b = math.factorial(4 * k) * (1103 + 26390 * k)
        c = pow(math.factorial(k), 4) * pow(396, 4 * k)
        x = x + a * b / c
    return str(1 / x)


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    oxy.StdioMCPClient(
        name="time",
        params={
            "command": "uvx",
            "args": ["mcp-server-time", "--local-timezone=Asia/Shanghai"],
        },
    ),
    math_fh,
    oxy.ReActAgent(
        name="master_agent",
        sub_agents=["time_agent", "math_agent"],
        is_master=True,
        llm_model="default_llm",
    ),
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool for time query",
        tools=["time"],
        llm_model="default_llm",
        team_size=2,
    ),
    oxy.WorkflowAgent(
        name="math_agent",
        desc="A tool for pi query",
        sub_agents=["time_agent"],
        tools=["math_tools"],
        func_workflow=workflow,
        llm_model="default_llm",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        res = await mas.call(
            callee="master_agent", arguments={"query": "The 30 positions of pi."}
        )
        print("=== User visiable output ===")
        print(res)


if __name__ == "__main__":
    asyncio.run(main())
