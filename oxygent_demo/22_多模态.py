import os
from oxygent import MAS, oxy


oxy_space = [
    oxy.HttpLLM(   # 注册多模态大模型
        name="default_vlm",
        api_key=os.getenv("DEFAULT_VLM_API_KEY"),
        base_url=os.getenv("DEFAULT_VLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_VLM_MODEL_NAME"),
        is_multimodal_supported=True,   # 申明多模态大模型
        is_convert_url_to_base64=True,   # 自动转base64编码
    ),
    oxy.ReActAgent(
        name="master_agent",
        llm_model="default_vlm",   # 配置多模态大模型
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="这是什么")   # 前端上传图片附件

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
