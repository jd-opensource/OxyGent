import asyncio
import os

from oxygent import MAS, Config, oxy, preset_tools

Config.set_agent_llm_model("default_llm")

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    preset_tools.train_ticket_tools,
    oxy.ReActAgent(
        name="train_ticket_agent",
        desc="A tool for train ticket",
        is_master=True,
        tools=["train_ticket_tools"],
        trust_mode=False,
        timeout=100,
    )
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="请帮我查询明天从西安到北京的火车票",
            welcome_message="您好我是火车票查询智能体，非常高兴为您服务。您可以这样问我：\n"
                            "\"明天从西安到北京的火车票\"\n"
                            "\"下周一上海到北京的卧铺火车票\"\n"
                            "\"后天西安到杭州的火车票多少钱\"\n"
                            "\"明天北京到西安的火车最短运行时间是多长\"\n\n"
                            "Hello, I am a train ticket inquiry assistant, and I am very happy to assist you. "
                            "You can ask me questions like:\n"
                            "\"Train tickets from Xi'an to Beijing tomorrow\"\n"
                            "\"Sleeper train tickets from Shanghai to Beijing next Monday\"\n"
                            "\"How much are train tickets from Xi'an to Hangzhou the day after tomorrow\"\n"
                            "\"What is the shortest travel time for trains from Beijing to Xi'an tomorrow\"\n"
        )


if __name__ == "__main__":
    asyncio.run(main())
