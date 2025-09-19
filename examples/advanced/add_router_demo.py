import asyncio
import os

import httpx
from fastapi import APIRouter

from oxygent import MAS, OxyRequest, oxy
from oxygent.schemas import WebResponse

router = APIRouter()


@router.get("/api_name")
def api_name():
    return WebResponse(data={"key": "value"}).to_dict()


async def workflow(oxy_request: OxyRequest):
    async with httpx.AsyncClient() as client:
        response = await client.get(url="http://127.0.0.1:8080/api_name")
        return response.json()


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
    ),
    oxy.WorkflowAgent(
        name="master_agent",
        llm_model="default_llm",
        func_workflow=workflow,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space, routers=[router]) as mas:
        await mas.start_web_service(first_query="hello")


if __name__ == "__main__":
    asyncio.run(main())
