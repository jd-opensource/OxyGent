import asyncio
from oxygent import oxy, MAS
from oxygent.utils.env_utils import get_env_var

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        semaphore=2,  # limit concurrency to 2(you can adjust this value to compare the performance of different concurrency limits)
    ),
    oxy.ChatAgent(
        name="test_agent",
        llm_model="default_llm",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        # call the agent
        tasks = [
            mas.call("test_agent", {"query": "repeat 20 times: hello"}),
            mas.call("test_agent", {"query": "repeat 20 times: world"}),
            mas.call("test_agent", {"query": "repeat 20 times: OxyGent"}),
            mas.call("test_agent", {"query": "repeat 20 times: concurrency"}),
            mas.call("test_agent", {"query": "repeat 20 times: test"}),
            mas.call("test_agent", {"query": "repeat 20 times: asyncio"}),
            mas.call("test_agent", {"query": "repeat 20 times: semaphore"}),
            mas.call("test_agent", {"query": "repeat 20 times: performance"}),
            mas.call("test_agent", {"query": "repeat 20 times: limit"}),
            mas.call("test_agent", {"query": "repeat 20 times: example"}),
            mas.call("test_agent", {"query": "repeat 20 times: code"}),
        ]

        results = await asyncio.gather(*tasks)
        for result in results:
            print(result)


if __name__ == "__main__":
    asyncio.run(main())
