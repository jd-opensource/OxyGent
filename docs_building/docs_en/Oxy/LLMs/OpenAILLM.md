# OpenAILLM

## Overview

`OpenAILLM` is a concrete implementation of the `RemoteLLM` class specifically designed for OpenAI's language models. It uses the official AsyncOpenAI client for optimal performance and compatibility with OpenAI's API standards. This class provides seamless integration with OpenAI's chat completion API, supporting all OpenAI models and compatible APIs.

## Class Hierarchy

<html>
    <h2 align="center">
      <img src="https://storage.jd.com/opponent/AI/1.png" width="50%"/>
    </h2>
</html>


## Features

The `OpenAILLM` class provides the following core functionalities:

1. **Official Client Integration**:
   - Uses the official AsyncOpenAI client library
   - Optimized for performance with OpenAI's API
   - Full compatibility with OpenAI's API standards

2. **Advanced Request Handling**:
   - Dynamic payload construction
   - Configuration merging from multiple sources
   - Parameter passing from request arguments

3. **Streaming Support**:
   - Real-time content delivery
   - Incremental message forwarding
   - Thinking process extraction during streaming

4. **Response Processing**:
   - Unified response format
   - Proper handling of completion responses
   - Support for reasoning content extraction

## Method Details

| Method | Async | Return Type | Purpose |
| ------ | ----------------- | ------------ | ------- |
| `_execute(oxy_request)` | Yes | `OxyResponse` | Executes a request using the OpenAI API, handling payload construction, configuration merging, and response processing |

## Parameter Details

| Parameter | Type/Allowed Values | Default | Description |
| --------- | -------------------- | ------- | ----------- |
| `api_key` | `Optional[str]` | `None` | The API key for authentication with OpenAI |
| `base_url` | `Optional[str]` | `""` | The base URL endpoint for the OpenAI API (can be used for compatible APIs) |
| `model_name` | `Optional[str]` | `""` | The specific OpenAI model name to use for requests (e.g., "gpt-4", "gpt-3.5-turbo") |
| `headers` | `Dict[str, str]` or `Callable[[OxyRequest], Dict[str, str]]` | `lambda oxy_request: {}` | Extra HTTP headers or a function that returns headers |

## Usage Example

Here's a basic example of how to use the `OpenAILLM` class:

```python
from oxygent.oxy.llms.openai_llm import OpenAILLM
from oxygent.schemas import OxyRequest

# Create an instance of OpenAILLM
openai_llm = OpenAILLM(
    api_key="your-openai-api-key",
    base_url="https://api.openai.com/v1",
    model_name="gpt-4",
    timeout=60
)

# Create a request
request = OxyRequest(
    messages=[{"role": "user", "content": "Hello, how are you?"}]
)

# Execute the request
response = await openai_llm.execute(request)

# Access the response
print(response.output)
```


## Notes

- `OpenAILLM` uses the official AsyncOpenAI client for optimal performance and compatibility
- The class supports both streaming and non-streaming responses
- When streaming is enabled, content is incrementally forwarded to the client
- The class has special handling for thinking process extraction during streaming:
  - Detects `reasoning_content` in the response
  - Automatically wraps reasoning content with `<think>` and `</think>` tags
  - Forwards thinking content to the frontend in real-time
- Configuration is merged from multiple sources in the following order of precedence:
  1. Request arguments (highest priority)
  2. Instance-specific LLM parameters
  3. Global LLM configuration
- The class is designed to work with all OpenAI models and compatible APIs
- For streaming responses, the class accumulates the complete response while forwarding incremental updates