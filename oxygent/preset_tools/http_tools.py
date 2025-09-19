import json
from typing import Optional, Dict, Any
from pydantic import Field
import httpx
from oxygent.oxy import FunctionHub
import asyncio

http_tools = FunctionHub(name="http_tools")


@http_tools.tool(
    description="Make a GET request to a specified URL with optional headers and parameters"
)
def http_get(
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    发送HTTP GET请求
    """
    try:
        # 使用同步客户端
        with httpx.Client() as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return json.dumps({
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": response.text
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@http_tools.tool(
    description="Make a POST request to a specified URL with optional headers and JSON data"
)
def http_post(
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
) -> str:
    """
    发送HTTP POST请求
    """
    try:
        # 确保Content-Type设置为application/json
        if headers is None:
            headers = {}
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        # 使用同步客户端
        with httpx.Client() as client:
            response = client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return json.dumps({
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": response.text
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def main():
    # GET请求示例
    result = await http_get("https://www.json.cn/", params={"key": "value"})
    print("GET Result:", result)

    # POST请求示例
    data = {"name": "test", "value": 123}
    result = await http_post("https://httpbin.org/post", data=data)
    print("POST Result:", result)

if __name__ == '__main__':
    asyncio.run(main())
