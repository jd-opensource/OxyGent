"""
启动 OxyGent Web 服务 - K2 模型 + Playwright 浏览器自动化
"""

import asyncio
import os
import sys
sys.path.append('/Users/melon/Documents/codes/OxyGent')
from oxygent import MAS, Config, oxy, preset_tools
from rate_limited_llm import RateLimitedHttpLLM


async def main():
    """启动 Web 服务，集成 K2 模型和 Playwright 浏览器自动化工具"""

    print("🚀 启动 OxyGent Web 服务 - K2 + Playwright 集成")
    print("=" * 60)

    # 检查环境变量
    api_key = os.getenv("DEFAULT_LLM_API_KEY")
    base_url = os.getenv("DEFAULT_LLM_BASE_URL")
    model_name = os.getenv("DEFAULT_LLM_MODEL_NAME")
    
    print(f"📋 配置信息:")
    print(f"   API Key: {api_key[:20]}..." if api_key else "   API Key: 未设置")
    print(f"   Base URL: {base_url}")
    print(f"   Model: {model_name}")
    print()

    if not api_key:
        print("⚠️  请先设置环境变量:")
        print("   export DEFAULT_LLM_API_KEY='your-api-key'")
        print("   export DEFAULT_LLM_BASE_URL='https://api.moonshot.cn/v1'")
        print("   export DEFAULT_LLM_MODEL_NAME='moonshot-v1-128k'")
        return

    # 配置 LLM
    Config.set_agent_llm_model("kimi_k2")

    oxy_space = [
        # LLM 配置 - 使用自定义的限频处理 LLM
        RateLimitedHttpLLM(
            name="kimi_k2",
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            llm_params={"temperature": 0.01},
            semaphore=1,  # 严格单线程
            timeout=120,  # 增加超时时间到 2 分钟
        ),
        
        # 原有工具保留
        oxy.ChatAgent(name="intent_agent"),
        
        # 原有 MCP 工具
        oxy.StdioMCPClient(
            name="time",
            params={
                "command": "uvx",
                "args": ["mcp-server-time", "--local-timezone=Asia/Shanghai"],
            },
        ),
        oxy.StdioMCPClient(
            name="filesystem",
            params={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "./local_file"],
            },
        ),
        oxy.StdioMCPClient(
            name="my_tools",
            params={
                "command": "uv",
                "args": ["--directory", "./mcp_servers", "run", "my_tools.py"],
            },
        ),
        
        # 添加浏览器自动化工具
        preset_tools.browser_automation_tools,
        
        # 原有智能体
        oxy.ReActAgent(
            name="time_agent",
            desc="A tool for time query.",
            tools=["time"],
            timeout=10,
        ),
        oxy.ReActAgent(
            name="file_agent",
            desc="A tool for file operation.",
            tools=["filesystem"],
        ),
        oxy.ReActAgent(
            name="math_agent",
            desc="A tool for math and calculation",
            tools=["my_tools"],
        ),
        
        # 新增浏览器智能体
        oxy.ReActAgent(
            name="browser_agent",
            desc="具备网页浏览和自动化能力的智能体。可以访问网站、提取内容、截图、获取链接、填写表单等浏览器操作。",
            tools=["browser_automation_tools"],
        ),
        
        # 主控智能体 - 包含所有子智能体，优化 API 调用
        oxy.ReActAgent(
            is_master=True,
            name="master_agent",
            desc="主控智能体，协调各种任务。具备时间查询、文件操作、数学计算、网页浏览等全面能力。",
            sub_agents=["time_agent", "file_agent", "math_agent", "browser_agent"],
            additional_prompt="You have access to multiple specialized agents: time_agent for time queries, file_agent for file operations, math_agent for calculations, and browser_agent for web browsing and automation. Choose the most appropriate agent for each task. IMPORTANT: After receiving a response from a sub-agent, directly return that response to the user without additional processing to minimize API calls.",
            timeout=180,  # 增加超时时间适应慢速 API
            llm_model="kimi_k2",
            delay=5.0,    # 智能体级别的延迟
            retries=3,    # 智能体级别的重试
        ),
    ]

    async with MAS(oxy_space=oxy_space) as mas:
        print("\n🌐 启动 Web 服务...")
        print("=" * 60)
        print("🎯 完整功能说明:")
        print("   - 🌙 Kimi K2 模型 (128K 上下文)")
        print("   - ⏰ 时间查询 (time_agent)")
        print("   - 📁 文件操作 (file_agent)")
        print("   - 🧮 数学计算 (math_agent)")
        print("   - 🌐 浏览器自动化 (browser_agent)")
        print("     * 网页导航、内容提取、截图、链接获取、表单填写")
        print("   - 🔄 智能任务路由和协调")
        print()
        print("💡 示例任务:")
        print("   - '现在几点了？'")
        print("   - '在本地文件中保存当前时间'")
        print("   - '计算圆周率的前10位'")
        print("   - '访问百度首页并告诉我页面标题'")
        print("   - '对知乎首页进行截图并保存到文件'")
        print("   - '访问某个网站，提取内容并保存到本地文件'")
        print("=" * 60)
        
        # 启动 Web 服务
        await mas.start_web_service(
            first_query="你好！我是集成了 Kimi K2 模型的全功能智能助手。我具备时间查询、文件操作、数学计算和浏览器自动化等多种能力。请告诉我你想要我做什么？",
            welcome_message="🌟 欢迎使用 OxyGent K2 全功能智能助手！\n\n我具备以下完整能力：\n⏰ 时间查询和时区转换\n📁 文件读写和管理\n🧮 数学计算和圆周率计算\n🌐 浏览器自动化：\n  • 网页导航和访问\n  • 页面内容提取\n  • 网页截图\n  • 链接提取\n  • 表单自动化\n\n请在下方输入您的需求，比如：\n• '现在几点了？'\n• '计算圆周率前10位'\n• '访问某个网站并获取信息'\n• '对网页进行截图并保存到文件'\n• '提取网页内容并保存到本地'"
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Web 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
