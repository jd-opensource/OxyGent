import asyncio
import os
import sys

# Ensure the project root is on sys.path so `oxygent` is importable from any working directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from oxygent import MAS, oxy, preset_tools

oxy_space = [
    # LLM
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
    ),
    # Tools
    preset_tools.shell_tools,
    # Skill Agent
    oxy.SkillAgent(
        name="skill_agent",
        llm_model="default_llm",
        tools=["execute_shell_command"],
        skills=["./skills"],
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="Review this code for bugs and security issues:\n\ndef login(user, pwd):\n    query = f\"SELECT * FROM users WHERE name='{user}' AND pass='{pwd}'\"\n    db.execute(query)\n    return True",
        )


if __name__ == "__main__":
    asyncio.run(main())
