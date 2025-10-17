# ChatAgent

## Overview

`ChatAgent` is a conversational agent module in the OxyGent framework, designed to handle dialogue interactions with language models. It inherits from the `LocalAgent` class and provides functionality for managing conversation memory, processing user queries, and coordinating with language models to generate responses.


## Functionality

`ChatAgent` is the most basic conversational agent in the OxyGent framework, with the following key features:

1. **Conversation Management**: Maintains conversation history, supporting multi-turn dialogues
2. **Prompt Configuration**: Default prompt is "You are a helpful assistant.", which can be customized
3. **Language Model Interaction**: Coordinates communication with the underlying language model
4. **Parameter Passing**: Supports passing custom parameters to the language model


## What Chat Agent does for you

ChatAgent is suitable for the following scenarios:

1. **Simple Q&A Systems**: Building basic question-answering bots to respond to user queries
2. **Customer Service Bots**: Handling common questions and user inquiries
3. **Personal Assistants**: Providing information lookup, simple task assistance, etc.
4. **Prototype Development and Testing**: Quickly building AI conversation system prototypes to validate concepts
5. **Educational Applications**: Creating interactive learning assistants to support teaching
6. **Component in Complex Systems**: Serving as a conversation processing module in larger systems
7. **Content Generation**: Generating text content such as copy, summaries, etc.


## Why use Chat Agent

1. **Simple to Use**: As a basic agent, it has a clean interface that's easy to learn and integrate
2. **Flexibility**: Supports custom prompts and parameters, allowing behavior adjustment as needed
3. **Lightweight**: Simple implementation without complex logic or dependencies, ensuring efficient operation
4. **Multi-turn Dialogue Support**: Maintains conversation history for coherent dialogue experiences
5. **Extensibility**: Can serve as a foundation component for more complex agents


## What Chat Agent is not suitable for

1. Tasks requiring complex reasoning and planning
2. Applications needing multi-step workflows
3. Systems requiring parallel processing of multiple tasks
4. Agents requiring highly customized behaviors


## Method Details

| Method                        | Coroutine (async) | Return Value  | Purpose (concise)                                                                                                                                                                               |
| ----------------------------- | ----------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_execute(self, oxy_request)` | Yes               | `OxyResponse` | Builds a temporary conversation **memory**, appends the latest user query, merges any `llm_params`, and calls the configured LLM model; returns the model’s reply wrapped in an `OxyResponse`.  |


## Parameter Configuration

When creating a ChatAgent, the following parameters can be configured:

| Parameter           | Type | Description | Default Value |
|-----------          |------|-------------|---------------|
| `name`              | str  | Agent name | Required |
| `desc`              | str  | Agent description | Required |
| `llm_model`         | str | Language model identifier | Required |
| `prompt`            | str | System prompt | "You are a helpful assistant." |
| `short_memory_size` | int | Short-term memory size | Inherited from LocalAgent |


## Usage Example

```python
from oxygent import MAS, OxySpace
from oxygent.oxy import ChatAgent

# Create OxySpace and register ChatAgent
oxy_space = OxySpace()
oxy_space.register_agent(
    ChatAgent(
        name="chat_agent",
        desc="Basic chat agent",
        llm_model="default_llm",
        prompt="You are a helpful assistant."
    )
)

# Use ChatAgent for conversation
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        result = await mas.chat_with_agent(payload={"query": "Hello, please introduce yourself."})
        print(result.output)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```



## Related Links

- [How to Communicate with Agents](../../../docs/docs_zh/1_1_chat_with_agent.md)
- [Selecting LLM for Agents](../../../docs/docs_zh/1_2_select_llm.md)
- [How to Choose Agents](../../../docs/docs_zh/1_4_select_agent.md)