"""Demo for using OxyGent with browser tools."""

import asyncio
import os
import logging
from typing import Dict, Any

from oxygent import MAS, Config, oxy
from oxygent.prompts import SYSTEM_PROMPT

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 从环境变量加载配置
def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    required_vars = [
        "DEFAULT_LLM_API_KEY",
        "DEFAULT_LLM_BASE_URL",
        "DEFAULT_LLM_MODEL_NAME"
    ]
    
    config = {}
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value is None:
            missing_vars.append(var)
        config[var] = value
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    return config

# Browser-specific system prompt
BROWSER_SYSTEM_PROMPT = """
You are a helpful assistant that can use these tools:
${tools_description}

Choose the appropriate tool based on the user's question.
If no tool is needed, respond directly.
If answering the user's question requires multiple tool calls, call only one tool at a time. After the user receives the tool result, they will provide you with feedback on the tool call result.

Important instructions for browser operations:
1. When performing web operations:
   - Always verify URLs before visiting
   - Handle page loading states appropriately
   - Extract relevant information efficiently
   - Save important data to files when requested
   - Follow proper browser automation practices

2. When saving web content:
   - Format data appropriately before saving
   - Use clear file naming conventions
   - Include relevant metadata
   - Verify file save operations

3. When you need to use a tool, you must only respond with the exact JSON object format below, nothing else:
```json
{
    "think": "Your thinking (if analysis is needed)",
    "tool_name": "Tool name",
    "arguments": {
        "parameter_name": "parameter_value"
    }
}
```

4. When a tool is still executing, you must wait for its result before calling another tool.

5. When calling multiple tools in sequence, you MUST correctly pass context and information from previous tool results to subsequent tool calls:
   - Include relevant data from previous tool results in the arguments of your next tool call
   - Maintain state and context across multiple tool calls
   - If a tool returns data that will be needed by a future tool, you must store that data

After receiving the tool's response:
1. Transform the raw data into a natural conversational response
2. The answer should be concise but rich in content
3. Focus on the most relevant information
4. Use appropriate context from the user's question
5. Avoid simply repeating the raw data

Please only use the tools explicitly defined above.
"""

class BrowserDemo:
    """Browser demo implementation class."""
    
    def __init__(self):
        """Initialize the browser demo with configuration."""
        try:
            self.config = load_config()
            Config.set_agent_llm_model("default_llm")
            self.oxy_space = self._create_oxy_space()
        except Exception as e:
            logger.error(f"Failed to initialize BrowserDemo: {str(e)}")
            raise

    def _create_oxy_space(self) -> list:
        """Create and configure the oxy space with all required components."""
        try:
            return [
                self._create_http_llm(),
                self._create_browser_tools(),
                self._create_filesystem_tools(),
                self._create_browser_agent(),
                self._create_file_agent(),
                self._create_master_agent()
            ]
        except Exception as e:
            logger.error(f"Failed to create oxy space: {str(e)}")
            raise

    def _create_http_llm(self) -> oxy.HttpLLM:
        """Create and configure the HTTP LLM component."""
        return oxy.HttpLLM(
            name="default_llm",
            api_key=self.config["DEFAULT_LLM_API_KEY"],
            base_url=self.config["DEFAULT_LLM_BASE_URL"],
            model_name=self.config["DEFAULT_LLM_MODEL_NAME"],
            llm_params={"temperature": 0.01},
            semaphore=4,
            category="llm",
            class_name="HttpLLM",
            desc="Default language model",
            desc_for_llm="Default language model for text generation",
            is_entrance=False,
            is_permission_required=False,
            is_save_data=True,
            timeout=60,
            retries=3,
            delay=1,
            is_multimodal_supported=False,
        )

    def _create_browser_tools(self) -> oxy.StdioMCPClient:
        """Create and configure the browser tools component."""
        return oxy.StdioMCPClient(
            name="browser_tools",
            params={
                "command": "uv",
                "args": ["--directory", "./mcp_servers", "run", "browser_tools.py"],
            },
            category="tool",
            class_name="StdioMCPClient",
            desc="Browser tools for web operations",
            desc_for_llm="Tools for browser automation and web scraping",
            is_entrance=False,
            is_permission_required=False,
            is_save_data=True,
            timeout=30,
            retries=3,
            delay=1,
            friendly_error_text="Browser operation failed",
            semaphore=2
        )

    def _create_filesystem_tools(self) -> oxy.StdioMCPClient:
        """Create and configure the filesystem tools component."""
        return oxy.StdioMCPClient(
            name="filesystem",
            params={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "./local_file"],
            },
            category="tool",
            class_name="StdioMCPClient",
            desc="File system operations",
            desc_for_llm="Tools for file system operations",
            is_entrance=False,
            is_permission_required=False,
            is_save_data=True,
            timeout=30,
            retries=3,
            delay=1,
            friendly_error_text="File system operation failed",
            semaphore=2
        )

    def _create_browser_agent(self) -> oxy.ReActAgent:
        """Create and configure the browser agent component."""
        return oxy.ReActAgent(
            name="browser_agent",
            desc="A tool for browser operations like visiting URLs, getting page content, and analyzing web pages.",
            desc_for_llm="Agent for browser automation and web scraping",
            category="agent",
            class_name="ReActAgent",
            tools=["browser_tools"],
            llm_model="default_llm",
            prompt=BROWSER_SYSTEM_PROMPT,
            is_entrance=False,
            is_permission_required=False,
            is_save_data=True,
            timeout=30,
            retries=3,
            delay=1,
            is_multimodal_supported=False,
            semaphore=2
        )

    def _create_file_agent(self) -> oxy.ReActAgent:
        """Create and configure the file agent component."""
        return oxy.ReActAgent(
            name="file_agent",
            desc="A tool for file operation.",
            desc_for_llm="Agent for file system operations",
            category="agent",
            class_name="ReActAgent",
            tools=["filesystem"],
            llm_model="default_llm",
            prompt=SYSTEM_PROMPT,
            is_entrance=False,
            is_permission_required=False,
            is_save_data=True,
            timeout=30,
            retries=3,
            delay=1,
            is_multimodal_supported=False,
            semaphore=2
        )

    def _create_master_agent(self) -> oxy.ReActAgent:
        """Create and configure the master agent component."""
        return oxy.ReActAgent(
            name="master_agent",
            desc="Master agent for coordinating browser and file operations",
            desc_for_llm="Master agent that coordinates browser automation and file operations",
            category="agent",
            class_name="ReActAgent",
            sub_agents=["browser_agent", "file_agent"],
            is_master=True,
            llm_model="default_llm",
            prompt=SYSTEM_PROMPT,
            is_entrance=False,
            is_permission_required=False,
            is_save_data=True,
            timeout=100,
            retries=3,
            delay=1,
            is_multimodal_supported=False,
            semaphore=2
        )

    async def run_demo(self, query: str = "搜索'武汉市天气'，提取搜索结果的天气概览数据保存到`./local_file/weather.txt`"):
        """Run the browser demo with the specified query."""
        try:
            async with MAS(oxy_space=self.oxy_space) as mas:
                logger.info(f"Starting web service with query: {query}")
                await mas.start_web_service(first_query=query)
                logger.info("Web service completed successfully")
        except Exception as e:
            logger.error(f"Error running browser demo: {str(e)}")
            raise

async def main():
    """Main entry point for the browser demo."""
    try:
        demo = BrowserDemo()
        await demo.run_demo()
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())