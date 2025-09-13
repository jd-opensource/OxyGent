"""
Browser Automation Tools Demo with Baidu

This demo showcases the browser automation capabilities of OxyGent using Baidu,
including web navigation, content extraction, screenshots, and link extraction.

Features demonstrated:
- Navigate to Baidu homepage
- Extract page title content
- Get navigation links
- Take screenshot of the page
- Interactive browser automation tasks

Usage:
    python examples/advanced/browser_automation_demo.py

Requirements:
    - Set LLM environment variables (DEFAULT_LLM_API_KEY, etc.)
    - Install Playwright: pip install playwright && playwright install
"""

import asyncio
import os
from oxygent import MAS, Config, oxy, preset_tools


async def main():
    """Demonstrate browser automation tools usage with Baidu website."""

    print("🚀 Starting OxyGent Browser Automation Demo with Baidu")
    print("=" * 60)

    # Check if basic LLM config is available
    if not os.getenv("DEFAULT_LLM_API_KEY") and not os.getenv("DEFAULT_LLM_BASE_URL"):
        print("⚠️  Warning: No LLM configuration found in environment variables")
        print("   Please set DEFAULT_LLM_API_KEY and DEFAULT_LLM_BASE_URL")
        print("   Demo will continue but may not work without proper LLM setup")
        print()

    # Configure LLM
    Config.set_agent_llm_model("default_llm")

    oxy_space = [
        oxy.HttpLLM(
            name="default_llm",
            api_key=os.getenv("DEFAULT_LLM_API_KEY", ""),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL", ""),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME", ""),
        ),
        # Add browser automation tools
        preset_tools.browser_automation_tools,
        # Create an agent that can use browser tools
        oxy.ReActAgent(
            name="browser_agent",
            desc="An agent capable of web browsing and automation tasks",
            tools=["browser_automation_tools"],
        ),
        # Master agent to coordinate tasks
        oxy.ReActAgent(
            is_master=True,
            name="master_agent",
            sub_agents=["browser_agent"],
        ),
    ]

    async with MAS(oxy_space=oxy_space) as mas:
        print("\n🌐 Browser Automation Demo with Baidu Started")
        print("=" * 60)

        # Demo 1: Navigate to Baidu
        print("\n📍 Demo 1: Navigate to Baidu")
        response = await mas.execute(
            "Navigate to http://www.baidu.com and tell me the page title"
        )
        print(f"Response: {response.output}")

        # Demo 2: Extract content from Baidu
        print("\n📄 Demo 2: Extract content from Baidu")
        response = await mas.execute(
            "Go to http://www.baidu.com and extract the page title content"
        )
        print(f"Response: {response.output}")

        # Demo 3: Get links from Baidu
        print("\n🔗 Demo 3: Get links from Baidu")
        response = await mas.execute(
            "Visit http://www.baidu.com and get the main navigation links"
        )
        print(f"Response: {response.output}")

        # Demo 4: Take a screenshot of Baidu
        print("\n📸 Demo 4: Take a screenshot of Baidu")
        response = await mas.execute(
            "Take a screenshot of http://www.baidu.com and save it as 'baidu_screenshot.png'"
        )
        print(f"Response: {response.output}")

        # Interactive browser automation
        print("\n💬 Interactive Browser Automation")
        print("Now you can ask the agent to perform browser tasks!")
        print("\nExample queries you can try:")
        print("- 'Navigate to sina.com.cn and get the page title'")
        print("- 'Take a screenshot of zhihu.com'")
        print("- 'Get links from douban.com'")
        print("- 'Extract content from any Chinese website'")
        print("- Type 'exit' to quit")
        print("-" * 60)

        while True:
            user_query = input("\n🤖 Enter your browser task: ").strip()

            if user_query.lower() in ["exit", "quit", "bye", "q"]:
                break

            if not user_query:
                continue

            try:
                print(f"🔄 Executing: {user_query}")
                response = await mas.execute(user_query)
                print(f"✅ Result: {response.output}")
            except Exception as e:
                print(f"❌ Error: {e}")

        print("\n👋 Browser automation demo completed!")
        print("Thanks for trying OxyGent's browser automation tools!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Demo failed: {e}")
