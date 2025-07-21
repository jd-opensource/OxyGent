"""Demo for using OxyGent with multiple LLMs and an agent."""

import asyncio

from oxygent import MAS, Config, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_es_config(
    {
        "hosts": ["${PROD_ES_HOST_1}", "${PROD_ES_HOST_2}", "${PROD_ES_HOST_3}"],
        "user": "${PROD_ES_USER}",
        "password": "${ES_TEST_PASSWORD}",
    }
)
oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
        timeout=240,
    ),
    oxy.ReActAgent(
        name="master_agent",
        is_master=True,
        llm_model="default_llm",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "hello"},
        ]
        result = await mas.call(callee="master_agent", arguments={"messages": messages})
        print(result)


if __name__ == "__main__":
    asyncio.run(main())


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "hello"},
        ]
        result = await mas.call(callee="master_agent", arguments={"messages": messages})
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
