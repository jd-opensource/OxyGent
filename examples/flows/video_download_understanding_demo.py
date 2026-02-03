"""Workflow-based Reflexion Demo for OxyGent"""

import asyncio
import os

from oxygent import MAS, Config, OxyRequest, oxy

# Set LLM model
Config.set_agent_llm_model("default_llm")


# Reflexion Workflow Core Logic
async def video_analysis_workflow(oxy_request: OxyRequest):
    """
    工作流：B站搜索 -> 下载视频 -> 视频理解分析
    """
    user_query = oxy_request.get_query(master_level=True)
    print(f"== 收到工作流任务: {user_query} ==")

    # --- Step 1: 直接调用 Bilibili 搜索 ---
    # 要求它只返回一个最相关的视频 URL
    bilibili_search_prompt = f"""
    请在Bilibili中搜索与以下需求最相关的视频，并只返回最相关的一个视频的完整网页URL，不要返回任何多余文本：
    {user_query}
    """

    search_resp = await oxy_request.call(
        callee="bilibili_agent",
        arguments={"query": bilibili_search_prompt}
    )

    video_url = search_resp.output.strip()
    print(f"== Step 1 B站搜索结果: {video_url} ==")

    # --- Step 2: 下载视频 ---
    download_resp = await oxy_request.call(
        callee="bilibili_bangumi_agent",
        arguments={"query": video_url}
    )

    local_video_path = download_resp.output
    print(f"== Step 2 视频已下载至: {local_video_path} ==")

    # --- Step 3: 视频理解分析 ---
    analysis_prompt = f"""
    请详细分析位于 '{local_video_path}' 的视频内容，并回答用户的问题：
    {user_query}
    """

    analysis_resp = await oxy_request.call(
        callee="video_understanding_agent",
        arguments={"query": analysis_prompt}
    )

    final_result = analysis_resp.output
    print("== Step 3 分析完成 ==")

    return final_result


# Define oxy_space
oxy_space = [
    # LLM model
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
        timeout=240,
    ),
    # Worker Agent - responsible for generating initial answers
    oxy.ReActAgent(
        name="worker_agent",
        desc="Worker agent responsible for generating initial answers",
        llm_model="default_llm",
    ),
    # Reflexion Agent - responsible for evaluating answer quality
    oxy.ChatAgent(
        name="reflexion_agent",
        desc="Reflexion agent responsible for evaluating answer quality and providing improvement suggestions",
        llm_model="default_llm",
    ),
    # Math Expert Agent - specifically handles mathematical problems
    oxy.ChatAgent(
        name="math_expert_agent",
        desc="Mathematics expert providing detailed mathematical solutions",
        llm_model="default_llm",
    ),
    # Math Checker Agent - checks mathematical solutions
    oxy.ChatAgent(
        name="math_checker_agent",
        desc="Mathematics solution checker verifying the correctness of mathematical solutions",
        llm_model="default_llm",
    ),
    # General Reflexion Workflow Agent
    preset_tools.bilibili_tools,
    oxy.ReActAgent(
        name="bilibili_agent",
        desc="A tool that can perform baidu search.",
        tools=["bilibili_tools"],
    ),
    preset_tools.video_understanding_tools,
    oxy.ReActAgent(
        name="video_understanding_agent",
        desc="A tool can understand the video.",
        tools=["video_understanding_tools"],
    ),
]


async def main():
    """Start Web Service Demo"""
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="Calculate the area of a circle with radius 5."
        )


if __name__ == "__main__":
    asyncio.run(main())
