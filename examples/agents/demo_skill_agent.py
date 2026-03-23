import asyncio
import os

from oxygent import MAS, oxy, preset_tools


async def main():
    oxy_space = [
        oxy.HttpLLM(
            name="default_llm",
            api_key=os.getenv("DEFAULT_LLM_API_KEY"),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        ),
        preset_tools.shell_tools,
        oxy.SkillAgent(
            name="skill_agent",
            llm_model="default_llm",
            tools=["execute_shell_command"],  # view_text_file no longer needed
            skills=[".oxygent/skills"],  # Custom skill paths (skill tool auto-registered)
            # enable_project_skills=True,  # Also scans .oxygent/skills/ by default
        ),
    ]

    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="What skills do you have?")


if __name__ == "__main__":
    asyncio.run(main())
