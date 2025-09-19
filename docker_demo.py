"""Docker 部署专用的简化 demo，避开 MCP 工具问题"""

import asyncio
import os
from oxygent import MAS, Config, oxy, preset_tools
from oxygent.utils.env_utils import get_env_var

# 使用 Docker 环境配置
Config.load_from_json("./config.json", "docker")

# 简化的 oxy_space，不使用 MCP 工具
oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
    ),
    preset_tools.time_tools,
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool that can query the time",
        tools=["time_tools"],
        llm_model="default_llm",
    ),
    preset_tools.math_tools,
    oxy.ReActAgent(
        name="math_agent",
        desc="A tool that can perform mathematical calculations.",
        tools=["math_tools"],
        llm_model="default_llm",
    ),
    oxy.ReActAgent(
        is_master=True,
        name="master_agent",
        sub_agents=["time_agent", "math_agent"],
        llm_model="default_llm",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        # 不发送初始查询，避免启动时触发 API 限制
        await mas.start_web_service()


if __name__ == "__main__":
    asyncio.run(main())
