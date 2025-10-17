# HttpTool
---
The position of the class is:


```markdown
[Oxy](../agent/base_oxy.md)
├── [BaseTool](../tools/base_tools.md)
    ├── [MCPTool](../tools/mcp_tool.md)
    ├── [BaseMCPClient](../tools/base_mcp_client.md)
    │   ├──[StdioMCPClient](../tools/stdio_mcp_client.md)
    │   ├──[SSEMCPClient](../tools/sse_mcp_client.md)
    │   └──[StreamableMCPClient](../tools/streamable_mcp_client.md)
    ├── [HttpTool](../api_tools/http_tool.md)
    ├── [FunctionHub](../function_tools/function_hub.md)
    └── [FunctionTool](../function_tools/function_tool.md)
└── [BaseFlow](../agent/base_flow.md)
```

---

## Introduce

`HttpTool` is a tool class for making HTTP requests to external APIs and services in the OxyGent system. It supports configurable methods, headers, and parameters with proper timeout handling.

## Parameters


| Parameter | Type / Allowed value | Default | Description |
| --------- | -------------------- | ------- | ----------- |
| `method` | `str` | `"GET"` | HTTP method to use |
| `url` | `str` | `""` | Target URL for the HTTP request |
| `headers` | `dict` | `{}` | HTTP headers to include in the request |
| `default_params` | `dict` | `{}` | Default parameters that will be merged with request arguments |

## Methods


| Method | Coroutine (async) | Return Value | Purpose |
| ------ | ----------------- | ------------ | ------- |
| `_execute(oxy_request)` | Yes | `OxyResponse` | Execute the HTTP request with merged parameters and timeout handling |

## Inherited
 Please refer to the [BaseTool](../agent/base_tools.md) class for inherited parameters and methods.
 
## Usage
```python
import os

import httpx
from pydantic import Field

from oxygent import MAS, oxy


# Create a simple HTTP GET request function
async def http_get(url: str = Field(description="URL address for the request"), 
                  demo: str = Field(description="Demo parameter")) -> str:
    """Send HTTP GET request to the specified URL and add demo parameter"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params={"demo": demo})
        return response.text

# Create FunctionTool instance
http_tool_obj = oxy.FunctionTool(
    name="http_tool",
    desc="A tool that can send HTTP GET requests",
    # This is the key part, need to provide func_process parameter
    func_process=http_get
)

# Define oxy_space configuration
oxy_space = [
    http_tool_obj,
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.1},
    ),
    oxy.ReActAgent(
        name="http_agent",
        desc="An assistant that can send http requests",
        tools=["http_tool"],
        llm_model="default_llm"
    ),
    oxy.ReActAgent(
        name="master_agent",
        is_master=True,
        sub_agents=["http_agent"],
        llm_model="default_llm"
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="Access https://httpbin.org/get with parameter demo=test")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```