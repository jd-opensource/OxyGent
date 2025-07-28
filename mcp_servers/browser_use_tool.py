import os, sys
import asyncio

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append('..')

from pydantic import Field
from browser_use import Agent
from browser_use.llm import ChatOpenAI
from oxygent import oxy
import logging

logger = logging.getLogger(__name__)
bs = oxy.FunctionHub(name="browser_use_tool", timeout=900)


@bs.tool(description="A powerful browser automation tool that allows interaction with web pages through various "
                     "actions. Automatically browse the web and extract information based on a given task.")
async def browser_use_api(
        task: str = Field(description="The task to perform")
) -> str:
    model = ChatOpenAI(
        model=os.getenv('GPT_4O'),
        base_url=os.getenv('OPEN_AI_URL'),
        api_key=os.getenv('OPEN_AI_KEY'),
    )
    browser_agent = Agent(
        task=task,
        llm=model,
        enable_memory=False,
        page_extraction_llm=model,
    )

    async def main():
        # history = await browser_agent.run(max_steps=20)
        try:
            history = await asyncio.wait_for(browser_agent.run(max_steps=10), timeout=360)
        except asyncio.TimeoutError:
            return "Browser operation timed out after 5 minutes"
        contents = history.extracted_content()
        return "\n".join(contents)

    return await main()


if __name__ == '__main__':
    from dotenv import load_dotenv
    from pathlib import Path  # python3 only

    env_path = Path('../examples/gaia/') / '.env'
    load_dotenv(dotenv_path=env_path, verbose=True)
    asyncio.run(browser_use_api(
        'What was the day in 2024 when the official CNS twitter account posted a photo with four ELON MUSK? .'))
    print("running")
