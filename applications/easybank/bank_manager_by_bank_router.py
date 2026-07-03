import asyncio
import os

from fastapi import Body

from oxygent import MAS, BankRouter, Config, oxy

Config.set_server_port(8090)


router = BankRouter()

user_profile_dict = {
    "001": "Arlen, a student, likes music",
    "002": "Tom, a programmer, likes sports",
}


@router.post("/user_profile_retrieve", description="A tool for querying user profile")
def user_profile_retrieve(
    query: str = Body(description="query"),
    user_pin: str = Body(description="SystemArg.user_pin"),
    agent_pin: str = Body(description="SystemArg.agent_pin"),
):
    global user_profile_dict
    portrait = user_profile_dict.get(user_pin, "Nothing")
    return f"The current user profile is: {portrait}"


@router.post("/user_profile_deposit", description="A tool for updating user profile")
async def user_profile_deposit(
    content: str = Body(description="content"),
    user_pin: str = Body(description="SystemArg.user_pin"),
    agent_pin: str = Body(description="SystemArg.agent_pin"),
):
    global user_profile_dict
    output = await router.mas.call(
        callee="bank_manager",
        arguments={
            "query": "Please update the user profile.",
            "chat": content,
            "profile": user_profile_dict.get(user_pin, "Nothing"),
        },
    )
    user_profile_dict[user_pin] = output
    return output


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
    ),
    oxy.ChatAgent(
        name="bank_manager",
        llm_model="default_llm",
        prompt="You are an expert in user profiling. Please update and refine the current user profile by integrating our previous conversation:\n${chat}\nAnd the current user profile:\n${profile}",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space, routers=[router]) as mas:
        await mas.start_web_service()


if __name__ == "__main__":
    asyncio.run(main())
