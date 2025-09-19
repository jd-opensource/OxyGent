"""
测试浏览器交互模型 + Playwright 浏览器自动化集成
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from oxygent import MAS, Config, oxy, preset_tools


async def main():
    """测试浏览器交互模型与浏览器自动化工具的集成"""

    print("🚀 启动 OxyGent 浏览器交互模型 + Playwright 集成测试")
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
    Config.set_agent_llm_model("browser_interaction_llm")

    oxy_space = [
        oxy.HttpLLM(
            name="browser_interaction_llm",
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
        ),
        # 添加浏览器自动化工具
        preset_tools.browser_automation_tools,
        # 创建具备浏览器能力的智能体
        oxy.ReActAgent(
            name="browser_agent",
            desc="具备网页浏览和自动化能力的智能体，使用浏览器交互模型",
            tools=["browser_automation_tools"],
        ),
        # 主控智能体
        oxy.ReActAgent(
            is_master=True,
            name="master_agent",
            sub_agents=["browser_agent"],
        ),
    ]

    async with MAS(oxy_space=oxy_space) as mas:
        print("\n🌐 浏览器交互模型 + Playwright 集成测试开始")
        print("=" * 60)

        # 测试 1: 简单的网页导航
        print("\n📍 测试 1: 使用浏览器交互模型进行网页导航")
        try:
            response = await mas.chat_with_agent({
                "query": "请访问 https://httpbin.org 并告诉我页面标题"
            })
            print(f"✅ 结果: {response.output}")
        except Exception as e:
            print(f"❌ 错误: {e}")

        # 测试 2: 内容提取
        print("\n📄 测试 2: 使用浏览器交互模型进行内容提取")
        try:
            response = await mas.chat_with_agent({
                "query": "访问 https://httpbin.org 并提取主要内容"
            })
            print(f"✅ 结果: {response.output}")
        except Exception as e:
            print(f"❌ 错误: {e}")

        # 测试 3: 截图功能
        print("\n📸 测试 3: 使用浏览器交互模型进行网页截图")
        try:
            response = await mas.chat_with_agent({
                "query": "对 https://httpbin.org 进行截图并保存为 browser_interaction_test_screenshot.png"
            })
            print(f"✅ 结果: {response.output}")
        except Exception as e:
            print(f"❌ 错误: {e}")

        print("\n🎯 交互式测试")
        print("现在您可以输入任何浏览器自动化任务，浏览器交互模型会帮您执行！")
        print("示例:")
        print("- '访问百度首页并获取标题'")
        print("- '对知乎首页进行截图'")
        print("- '获取豆瓣网的主要链接'")
        print("- 输入 'exit' 退出")
        print("-" * 60)

        while True:
            user_input = input("\n🤖 请输入测试任务: ").strip()
            
            if user_input.lower() in ['exit', 'quit', '退出', 'q']:
                break
                
            if not user_input:
                continue
                
            try:
                print(f"🔄 浏览器交互模型正在处理: {user_input}")
                response = await mas.chat_with_agent({"query": user_input})
                print(f"✅ 浏览器交互模型 + Playwright 结果: {response.output}")
            except Exception as e:
                print(f"❌ 执行错误: {e}")

        print("\n👋 浏览器交互模型 + Playwright 集成测试完成!")
        print("感谢使用 OxyGent 的浏览器交互模型 + 浏览器自动化功能!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
