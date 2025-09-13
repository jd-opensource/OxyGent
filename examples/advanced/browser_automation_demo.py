

import asyncio
import os
from oxygent import MAS, Config, oxy, preset_tools


async def main():
    """Demonstrate browser automation tools usage."""
    
    # Configure LLM
    Config.set_agent_llm_model("default_llm")
    
    oxy_space = [
        oxy.HttpLLM(
            name="default_llm",
            api_key=os.getenv("DEFAULT_LLM_API_KEY", "your-api-key-here"),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL", ""),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME", "gpt-4o"),
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
        print("🌐 Browser Automation Demo Started")
        print("=" * 50)
        
        # Demo 1: Navigate to a webpage
        print("\n📍 Demo 1: Navigate to a webpage")
        response = await mas.execute(
            "Navigate to https://httpbin.org and tell me the page title"
        )
        print(f"Response: {response.output}")
        
        # Demo 2: Extract content from a webpage
        print("\n📄 Demo 2: Extract content from a webpage")
        response = await mas.execute(
            "Go to https://httpbin.org and extract the main content from the page"
        )
        print(f"Response: {response.output}")
        
        # Demo 3: Get all links from a webpage
        print("\n🔗 Demo 3: Get links from a webpage")
        response = await mas.execute(
            "Visit https://httpbin.org and get all the links on the page"
        )
        print(f"Response: {response.output}")
        
        # Demo 4: Take a screenshot
        print("\n📸 Demo 4: Take a screenshot")
        response = await mas.execute(
            "Take a screenshot of https://httpbin.org and save it as 'httpbin_screenshot.png'"
        )
        print(f"Response: {response.output}")
        
        while True:
            user_query = input("Enter your browser task: ").strip()
            
            if user_query.lower() in ['exit', 'quit', 'bye']:
                break
            
            if not user_query:
                continue
                
            try:
                response = await mas.execute(user_query)
                print(f"Result: {response.output}")
            except Exception as e:
                print(f"Error: {e}")
        
        print("Browser automation demo completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Demo failed: {e}")
