# quickStart
Oxygent is a Python library designed to simplify the development of multi-agent systems (MAS) using OpenAI's GPT models. It provides a straightforward interface for creating agents, managing their interactions, and handling tasks like vector databases and embedding caching.

## Build the OxyGent environment
This guide demonstrates how to set up your environment and run a simple example using the Oxygen Multi-Agent System (MAS) framework. The steps below will walk you through installing dependencies, configuring your environment, and executing a sample script.

### Step 1: Create and Activate a Python Environment

> ⚠️ Note: OxyGent only supports Python 3.10 and above.  
> Please ensure that your Python environment version is at least 3.10, otherwise it may not run properly.

It is recommended to use a dedicated Python environment for your project. You can create and activate an environment using the following methods:

#### conda
```bash
conda create -n oxy_env python==3.10
conda activate oxy_env
```

#### venv
```bash
python -m venv .venv
source .venv/bin/activate
```

#### uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.10 
uv venv .venv --python 3.10
source .venv/bin/activate
```

### Step 2: Install Required Python Package
After activating your environment, install the required Python package with:
```bash
pip install oxygent
```
If you use uv to create the environment, use the following command:
```bash
uv pip install oxygent
```

### Step 3: Sample Python Script
Below is a sample Python script (demo.py) that demonstrates how to use the Oxygen MAS framework. This script initializes a MAS instance and starts a web service that handles a simple query.
```python
import os

from oxygent import MAS, Config, oxy
from oxygent import preset_tools

time_tools = preset_tools.time_tools
math_tools = preset_tools.math_tools
file_tools = preset_tools.file_tools

Config.set_agent_llm_model("default_llm")

oxy_space = [
    oxy.HttpLLM(
        name='default_llm',
        api_key=os.getenv('DEFAULT_LLM_API_KEY'),
        base_url=os.getenv('DEFAULT_LLM_BASE_URL'),
        model_name=os.getenv('DEFAULT_LLM_MODEL_NAME'),
        llm_params={
            'temperature': 0.01
        },
        semaphore=4
    ),
    time_tools,
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool that can query the time",
        tools=["time_tools"],
    ),
    file_tools,
    oxy.ReActAgent(
        name="file_agent",
        desc="A tool that can operate the file system",
        tools=["file_tools"],
    ),
    math_tools,
    oxy.ReActAgent(
        name='math_agent',
        desc='A tool that can perform mathematical calculations.',
        tools=['math_tools'],
    ),
    oxy.ReActAgent(
        is_master=True,
        name="master_agent",
        sub_agents=["time_agent", "file_agent", "math_agent"],
    ),
]


async def main():


    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="What time is it now? Please save it into time.txt.")

if __name__ == "__main__":
    import asyncio

asyncio.run(main())
```

### Step 4: Configure Your LLM Settings
Before running the script, set the following environment variables to configure your Large Language Model (LLM) service:
```bash
export DEFAULT_LLM_API_KEY="your_api_key"
export DEFAULT_LLM_BASE_URL="your_base_url"  # if you want to use a custom base URL
export DEFAULT_LLM_MODEL_NAME="your_model_name"
```

## Running the Oxygent example
> ⚠️ Note: For your best experience, it is recommended that you install [Node.js](https://nodejs.org/) first.

Execute the sample script using the following command:
```bash
python demo.py
```

View the output:
![](../../images/quickstart_chat.png)
You can click the output text under master_agent on the right to view the dynamically generated call flow chart.
![](../../images/quickstart_chat_flow_chat.png)

## What's Next
- :doc:`/user_guide/index`to learn how to use Oxygent
- :doc:`/api/oxygent.mas`to explore the API