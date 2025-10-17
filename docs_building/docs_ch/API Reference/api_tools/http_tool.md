# HttpTool
---
HttpTool在OxyGent中的位置是：


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

## 介绍

`HttpTool` 用于在Oxygent中对外部API和服务发起HTTP请求的工具类。它支持可配置的方法类型、请求头信息和参数，并且自带基本的超时处理。

## 参数


| 参数 | 类型     | 默认值     | 描述                                                            |
| --------- |--------|---------|---------------------------------------------------------------|
| `method` | `str`  | `"GET"` | 使用的HTTP方法                                            |
| `url` | `str`  | `""`    | 请求的目标URL                               |
| `headers` | `dict` | `{}`    | HTTP请求头                        |
| `default_params` | `dict` | `{}`    | 将合并到请求参数中的默认参数 |

## 方法


| 方法 | 协程（异步） | 返回值 | 用途                                                                  |
| ------ |--------| ------------ |---------------------------------------------------------------------|
| `_execute(oxy_request)` | 是      | `OxyResponse` | 使用合并的参数和超时处理执行HTTP请求 |

## 继承
 请参考[BaseTool](../agent/base_tools.md)类了解集成的参数和方法。
 
## 使用方法
```python
import os

import httpx
from pydantic import Field

from oxygent import MAS, oxy


# 创建一个简单的HTTP GET请求函数
async def http_get(url: str = Field(description="请求的URL地址"), 
                  demo: str = Field(description="演示参数")) -> str:
    """发送HTTP GET请求到指定URL，并添加demo参数"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params={"demo": demo})
        return response.text

# 创建FunctionTool实例
http_tool_obj = oxy.FunctionTool(
    name="http_tool",
    desc="一个可以发送HTTP GET请求的工具",
    # 这里是关键，需要提供func_process参数
    func_process=http_get
)

# 定义oxy_space配置
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
        desc="一个可以发送http请求的助手",
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
        await mas.start_web_service(first_query="访问https://httpbin.org/get，参数是demo=test")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```