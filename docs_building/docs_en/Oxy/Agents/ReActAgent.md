# ReActAgent

The ReActAgent implements the **ReAct (Reasoning and Acting)** paradigm, enabling autonomous agent behavior by combining language model reasoning with tool execution in an iterative loop.

## Overview

ReActAgent is OxyGent's most versatile agent for complex tasks requiring multiple tool interactions. It intelligently alternates between:

1. **Reasoning**: Using LLMs to analyze the task and decide next actions
2. **Acting**: Executing tools based on reasoning decisions
3. **Observing**: Processing tool results to inform next reasoning step

This cycle continues until the agent reaches a satisfactory answer or hits the maximum iteration limit.

## Quick Start

### Basic Usage

```python
import asyncio
from oxygent import MAS, oxy

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        base_url="your_base_url",
        api_key="your_api_key",
        model_name="your_model"
    ),
    oxy.FunctionTool(
        name="calculator",
        func=lambda x, y: x + y,
        description="Add two numbers"
    ),
    oxy.ReActAgent(
        name="assistant",
        is_master=True,
        llm_model="default_llm",
        tools=["calculator"]
    ),
]

async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        result = await mas.call(
            callee="assistant",
            arguments={
                "messages": [
                    {"role": "user", "content": "What is 25 + 17?"}
                ]
            }
        )
        print(result.output)

asyncio.run(main())
```

### With Multiple Tools

```python
from oxygent import preset_tools

oxy_space = [
    oxy.HttpLLM(name="default_llm", ...),
    preset_tools.math_tools,
    preset_tools.time_tools,
    preset_tools.http_tools,
    oxy.ReActAgent(
        name="multi_tool_agent",
        is_master=True,
        llm_model="default_llm",
        tools=["math_tools", "time_tools", "http_tools"],
        max_react_rounds=10
    ),
]
```

## Configuration Options

### Core Parameters

#### `max_react_rounds` (int, default: 16)

Maximum number of reasoning-acting iterations before fallback mechanism activates.

```python
oxy.ReActAgent(
    name="patient_agent",
    max_react_rounds=25,  # Allow more iterations for complex tasks
    ...
)
```

**When to adjust**:

- Increase for complex multi-step tasks
- Decrease for simple tasks to save costs
- Monitor actual rounds used via logs

#### `llm_model` (str, required)

Name of the LLM component to use for reasoning.

```python
oxy_space = [
    oxy.HttpLLM(name="fast_model", model_name="gpt-3.5-turbo", ...),
    oxy.HttpLLM(name="smart_model", model_name="gpt-4", ...),
    oxy.ReActAgent(
        name="agent",
        llm_model="smart_model",  # Use more capable model
        ...
    ),
]
```

#### `tools` (list[str])

List of tool names the agent can use. Tools must be registered in the same MAS.

```python
oxy.ReActAgent(
    name="agent",
    tools=["web_search", "calculator", "file_reader"],
    ...
)
```

### Memory Management

#### `is_discard_react_memory` (bool, default: True)

Controls how conversation history is stored:

- **True**: Simple mode - only keeps final question-answer pairs
- **False**: Advanced mode - retains detailed ReAct reasoning steps with weighted scoring

```python
# Simple mode (recommended for most use cases)
oxy.ReActAgent(
    name="simple_agent",
    is_discard_react_memory=True,  # Clean history
    ...
)

# Advanced mode (for debugging or complex reasoning chains)
oxy.ReActAgent(
    name="detailed_agent",
    is_discard_react_memory=False,  # Keep full reasoning trace
    memory_max_tokens=30000,
    weight_short_memory=5,
    weight_react_memory=1,
    ...
)
```

#### `memory_max_tokens` (int, default: 24800)

Maximum tokens for memory management when `is_discard_react_memory=False`.

```python
oxy.ReActAgent(
    name="agent",
    is_discard_react_memory=False,
    memory_max_tokens=50000,  # Larger context for detailed history
    ...
)
```

#### `weight_short_memory` (int, default: 5)

Priority weight for short-term memory (final answers) when selecting which memories to retain.

#### `weight_react_memory` (int, default: 1)

Priority weight for ReAct memory (intermediate reasoning steps).

```python
oxy.ReActAgent(
    name="agent",
    weight_short_memory=10,  # Strongly prefer final answers
    weight_react_memory=1,   # Lower priority for intermediate steps
    ...
)
```

### Advanced Features

#### `trust_mode` (bool, default: False)

When enabled, allows the agent to return tool results directly without additional reasoning.

```python
oxy.ReActAgent(
    name="trusted_agent",
    trust_mode=True,  # Fast path for trusted tools
    ...
)
```

**Use cases**:

- Database queries that return formatted results
- API calls that provide final answers
- Tools with built-in result formatting

**How it works**:

- Agent can include `"trust_mode": 1` in tool call
- Tool result is returned immediately as final answer
- Skips additional LLM reasoning on the result

#### `prompt` (str, optional)

Custom system prompt to override default behavior.

```python
custom_prompt = """You are a specialized data analyst agent.
You have access to SQL and visualization tools.
Always validate data before visualization."""

oxy.ReActAgent(
    name="data_agent",
    prompt=custom_prompt,
    tools=["sql_tools", "chart_tools"],
    ...
)
```

#### `func_parse_llm_response` (Callable, optional)

Custom function to parse LLM outputs into structured responses.

```python
def custom_parser(response: str, request: OxyRequest) -> LLMResponse:
    # Custom parsing logic
    if "FINAL:" in response:
        return LLMResponse(
            state=LLMState.ANSWER,
            output=response.split("FINAL:")[-1].strip(),
            ori_response=response
        )
    # ... tool call parsing logic
    return default_parse(response)

oxy.ReActAgent(
    name="agent",
    func_parse_llm_response=custom_parser,
    ...
)
```

#### `func_reflexion` (Callable, optional)

Custom validation function to check if agent responses are acceptable.

```python
def custom_reflexion(response: str, request: OxyRequest) -> str:
    """Return error message if response is invalid, None if valid."""
    if len(response) < 10:
        return "Response too short. Provide more details."
    if "error" in response.lower():
        return "Response contains error. Please try again."
    return None  # Response is acceptable

oxy.ReActAgent(
    name="quality_controlled_agent",
    func_reflexion=custom_reflexion,
    ...
)
```

## Tool Retrieval Modes

ReActAgent supports three modes for managing large tool sets:

### Mode 1: No Retrieval (All Tools)

Return all available tools regardless of count.

```python
oxy.ReActAgent(
    name="agent",
    top_k_tools=float('inf'),
    is_retrieve_even_if_tools_scarce=False,
    tools=["tool1", "tool2", "tool3", ...],  # All provided
)
```

**Best for**: Small tool sets (< 20 tools)

### Mode 2: Query-Based Retrieval

Automatically retrieve top N most relevant tools based on the query.

```python
oxy.ReActAgent(
    name="agent",
    top_k_tools=5,  # Only provide 5 most relevant tools per query
    tools=["tool1", "tool2", ..., "tool100"],
)
```

**Best for**: Large tool sets where query relevance is clear

**Requirements**: Vearch vector database configured in config.json

### Mode 3: Active Sourcing

Provide a special "retrieve_tools" tool that the agent can invoke to search for relevant tools dynamically.

```python
oxy.ReActAgent(
    name="agent",
    is_sourcing_tools=True,
    top_k_tools=5,
    tools=["tool1", "tool2", ..., "tool100"],
)
```

**Best for**: Complex tasks where initial query doesn't reveal needed tools

**How it works**:

- Agent receives limited initial tool set
- Can call `retrieve_tools` with search query
- Gets additional relevant tools dynamically

## Understanding ReAct Execution Flow

### Normal Execution Cycle

```
User Query
    ↓
┌─────────────────────────┐
│  1. Reasoning (LLM)     │ ← System Prompt + History + Query
│  Decides next action    │
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│  2. Action (Tool Call)  │ ← Execute tool(s)
│  or Final Answer        │
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│  3. Observation         │ ← Tool results
│  Add to ReAct memory    │
└─────────────────────────┘
    ↓
  Repeat until answer or max_react_rounds
    ↓
Final Answer
```

### Fallback Mechanism

If `max_react_rounds` is reached without final answer:

1. Collect all tool execution results from ReAct memory
2. Create summary: "User question: {query}\nTool results: {results}"
3. Make final LLM call with simplified prompt
4. Return generated answer

**Example fallback scenario**:

```python
# Agent makes 16 tool calls but doesn't formulate final answer
# Fallback aggregates results:
"""
User question: What's the weather and news today?

Tool execution results:
1. Weather in NYC: 72°F, sunny
2. Top news: [article summaries]
...

Please answer based on these results.
"""
```

## Response Parsing

The agent expects LLM responses in specific formats:

### Tool Call Format

```json
{
  "thought": "I need to check the current time",
  "tool_name": "get_current_time",
  "arguments": {"timezone": "UTC"}
}
```

### Multiple Tool Calls

```json
[
  {
    "tool_name": "web_search",
    "arguments": {"query": "Python asyncio"}
  },
  {
    "tool_name": "web_search",
    "arguments": {"query": "Python multithreading"}
  }
]
```

### Final Answer Format

Plain text without JSON structure:

```
Based on the search results, asyncio is better for I/O-bound tasks
while multithreading is better for CPU-bound tasks...
```

### Think Tag Support

For models with thinking capability:

```
<think>
Let me analyze this step by step...
</think>

{"tool_name": "calculator", "arguments": {"x": 5, "y": 3}}
```

The agent automatically strips `<think>` tags before parsing.

## Best Practices

### 1. Choose Appropriate max_react_rounds

```python
# Simple single-tool tasks
oxy.ReActAgent(name="simple", max_react_rounds=3, ...)

# Multi-step research tasks
oxy.ReActAgent(name="researcher", max_react_rounds=20, ...)

# Complex reasoning chains
oxy.ReActAgent(name="planner", max_react_rounds=30, ...)
```

### 2. Memory Management Strategy

```python
# For production chatbots (clean history)
oxy.ReActAgent(
    name="chatbot",
    is_discard_react_memory=True,
    short_memory_size=10,  # Keep last 10 conversations
)

# For debugging/analysis (detailed trace)
oxy.ReActAgent(
    name="debug_agent",
    is_discard_react_memory=False,
    memory_max_tokens=50000,
)
```

### 3. Tool Organization

```python
# Group related tools
math_agent = oxy.ReActAgent(
    name="math_agent",
    tools=["calculator", "equation_solver", "statistics"],
    ...
)

# Use hierarchical agents for complex domains
main_agent = oxy.ReActAgent(
    name="main",
    sub_agents=["math_agent", "web_agent", "file_agent"],
    ...
)
```

### 4. Custom Reflexion for Quality Control

```python
def domain_validator(response: str, request: OxyRequest) -> str:
    """Validate responses for medical domain."""
    if not response:
        return "Response cannot be empty"

    # Domain-specific validation
    if "diagnosis" in response.lower() and "not a doctor" not in response.lower():
        return "Include medical disclaimer in diagnosis-related responses"

    if len(response) < 50:
        return "Provide more detailed medical information"

    return None

medical_agent = oxy.ReActAgent(
    name="medical_assistant",
    func_reflexion=domain_validator,
    ...
)
```

### 5. Trust Mode for Efficiency

```python
# Tool that returns formatted results
oxy_space = [
    oxy.HttpLLM(name="llm", ...),
    oxy.FunctionTool(
        name="get_user_info",
        func=lambda user_id: f"User {user_id}: John Doe, john@example.com",
        description="Get formatted user information"
    ),
    oxy.ReActAgent(
        name="agent",
        tools=["get_user_info"],
        trust_mode=True,  # Return tool result directly
        ...
    ),
]
```

## Common Patterns

### Pattern 1: Research Agent

```python
research_agent = oxy.ReActAgent(
    name="researcher",
    llm_model="gpt-4",
    tools=["web_search", "summarize", "save_file"],
    max_react_rounds=25,
    is_discard_react_memory=False,  # Keep research trail
    memory_max_tokens=40000,
)
```

### Pattern 2: Data Analysis Agent

```python
analyst = oxy.ReActAgent(
    name="data_analyst",
    llm_model="claude-3-sonnet",
    tools=["sql_tools", "chart_tools", "statistics_tools"],
    max_react_rounds=15,
    trust_mode=True,  # Trust SQL query results
)
```

### Pattern 3: Customer Support Agent

```python
support_agent = oxy.ReActAgent(
    name="support",
    llm_model="gpt-3.5-turbo",
    tools=["knowledge_base", "ticket_system", "email_tool"],
    max_react_rounds=8,
    is_discard_react_memory=True,  # Clean conversation history
    short_memory_size=20,  # Remember conversation context
)
```

## API Reference

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | Required | Unique identifier for the agent |
| `is_master` | bool | False | Whether this is the entry point agent |
| `llm_model` | str | Required | Name of LLM component to use |
| `tools` | list[str] | [] | List of tool names |
| `sub_agents` | list[str] | [] | List of sub-agent names |
| `max_react_rounds` | int | 16 | Maximum reasoning-acting iterations |
| `is_discard_react_memory` | bool | True | Discard detailed ReAct memory |
| `memory_max_tokens` | int | 24800 | Max tokens for memory |
| `weight_short_memory` | int | 5 | Priority weight for final answers |
| `weight_react_memory` | int | 1 | Priority weight for reasoning steps |
| `trust_mode` | bool | False | Enable direct tool result return |
| `prompt` | str | None | Custom system prompt |
| `func_parse_llm_response` | Callable | None | Custom response parser |
| `func_reflexion` | Callable | None | Custom validation function |
| `top_k_tools` | int | 10 | Number of tools to retrieve |
| `is_sourcing_tools` | bool | False | Enable dynamic tool retrieval |
| `short_memory_size` | int | 10 | Number of historical conversations to keep |

### Return Types

**OxyResponse**: Standard response object

```python
class OxyResponse:
    state: OxyState  # COMPLETED, ERROR, etc.
    output: str  # Final answer or error message
    extra: dict  # {"react_memory": [...]}
```

**LLMResponse**: Parsed LLM output

```python
class LLMResponse:
    state: LLMState  # ANSWER, TOOL_CALL, ERROR_PARSE
    output: str | dict | list  # Depends on state
    ori_response: str  # Original LLM text
```

## Others

## Multimodal Support

ReActAgent supports multimodal queries (text, images, video):

```python
result = await mas.call(
    callee="agent",
    arguments={
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
                ]
            }
        ]
    }
)
```

## Integration with Flows

Combine ReActAgent with advanced reasoning flows:

```python
from oxygent.oxy.flows import Reflexion

oxy_space = [
    oxy.HttpLLM(name="llm", ...),
    oxy.ReActAgent(name="base_agent", ...),
    Reflexion(
        name="reflexion_agent",
        is_master=True,
        agent_name="base_agent",
        max_iterations=3,
    ),
]
```
