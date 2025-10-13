Rag_agent  (Retrieval-Augmented Generation) conversational agent.
Before generating a response with a large language model, relevant external knowledge is retrieved through a search function and injected into the prompt to improve the accuracy and controllability of the answers.
## Overview
This module provides the ChatAgent class, which handles conversational AI interactions by managing conversation memory, processing user queries, and coordinating with language models to generate responses.
## Quick Start
### Basic Usage
OxyGent supports injecting knowledge into prompts via the knowledge parameter. Below is a simple example of RAG:
You need to first create a retrieval method:
```python
def retrieval(query):
    # Replace with the actual database
    return "\n".join(["knowledge1", "knowledge2", "knowledge3"])
```
Next, you need to inject the retrieved knowledge in update_query:
```python
def update_query(oxy_request: OxyRequest):
    current_query = oxy_request.get_query()

    def retrieval(query):
        return "\n".join(["knowledge1", "knowledge2", "knowledge3"])

    oxy_request.arguments["knowledge"] = retrieval(current_query) # Key Method
    return oxy_request
```
## Complete runnable example
Below is a complete runnable code example:
```python
import asyncio

from oxygent import MAS, OxyRequest, oxy
from oxygent.utils.env_utils import get_env_var

INSTRUCTION = """
You are a helpful assistant and can use these tools:
${tools_description}

Experience in choosing tools:
${knowledge}

Select the appropriate tool based on the user's question.
If no tool is needed, reply directly.
If answering the user's question requires calling multiple tools, call only one tool at a time. After the user receives the tool result, they will give you feedback on the tool call result.

Important notes:
1. When you have collected enough information to answer the user's question, please respond in the following format:
<think>Your reasoning (if analysis is needed)</think>
Your response content
2. When you find that the user's question lacks certain conditions, you can ask them back. Please respond in the following format:
<think>Your reasoning (if analysis is needed)</think>
Your follow-up question to the user
3. When you need to use a tool, you must respond **only** with the following exact JSON object format, and nothing else:

{
    "think": "Your reasoning (if analysis is needed)",
    "tool_name": "Tool name",
    "arguments": {
        "Parameter name": "Parameter value"
    }
}
"""


def update_query(oxy_request: OxyRequest):
    current_query = oxy_request.get_query()

    def retrieval(query):
        return "\n".join(["knowledge1", "knowledge2", "knowledge3"])

    oxy_request.arguments["knowledge"] = retrieval(current_query)
    return oxy_request


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
    ),
    oxy.ReActAgent(
        name="master_agent",
        is_master=True,
        llm_model="default_llm",
        timeout=100,
        prompt=INSTRUCTION,
        func_process_input=update_query,
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="This is an example for rag. Please modify it according to the specific needs",
        )

if __name__ == "__main__":
    asyncio.run(main())
```
## Configuration Options
### Core Parameters
#### knowledge
1.Call the externally injected retrieval function to obtain relevant knowledge based on the request content.
2.Write theretrieved knowledge into oxy_request.arguments under the placeholder key(knowledge_placeholder) for subsequent template rendering/prompt composition.
### retrieval(str)
Perform knowledge retrieval based on the current request(e.g., from a vector database, searchservice, or self-hosted knowledgebase)