# OpenAILLM

## 概述

`OpenAILLM` 是 `RemoteLLM` 类的一个具体实现，专为OpenAI的语言模型设计。它使用官方的AsyncOpenAI客户端，以获得最佳性能和与OpenAI API标准的兼容性。该类提供了与OpenAI聊天完成API的无缝集成，支持所有OpenAI模型和兼容的API。

## 类层次结构
<html>
    <h2 align="center">
      <img src="https://storage.jd.com/opponent/AI/2.png" width="50%"/>
    </h2>
</html>

## 功能特性

`OpenAILLM` 类提供以下核心功能：

1. **官方客户端集成**：
   - 使用官方AsyncOpenAI客户端库
   - 针对OpenAI的API性能进行优化
   - 与OpenAI的API标准完全兼容

2. **高级请求处理**：
   - 动态负载构建
   - 从多个来源合并配置
   - 从请求参数传递参数

3. **流式传输支持**：
   - 实时内容传递
   - 增量消息转发
   - 流式传输过程中的思考过程提取

4. **响应处理**：
   - 统一的响应格式
   - 正确处理完成响应
   - 支持推理内容提取

## 方法详情

| 方法 | 异步 | 返回类型 | 用途 |
| ------ | ----------------- | ------------ | ------- |
| `_execute(oxy_request)` | 是 | `OxyResponse` | 使用OpenAI API执行请求，处理负载构建、配置合并和响应处理 |

## 参数详情

| 参数 | 类型/允许值 | 默认值 | 描述 |
| --------- | -------------------- | ------- | ----------- |
| `api_key` | `Optional[str]` | `None` | 用于OpenAI身份验证的API密钥 |
| `base_url` | `Optional[str]` | `""` | OpenAI API的基础URL端点（可用于兼容的API） |
| `model_name` | `Optional[str]` | `""` | 用于请求的特定OpenAI模型名称（例如，"gpt-4"，"gpt-3.5-turbo"） |
| `headers` | `Dict[str, str]` 或 `Callable[[OxyRequest], Dict[str, str]]` | `lambda oxy_request: {}` | 额外的HTTP头或返回头的函数 |

## 使用示例

以下是如何使用 `OpenAILLM` 类的基本示例：

```python
from oxygent.oxy.llms.openai_llm import OpenAILLM
from oxygent.schemas import OxyRequest

# 创建OpenAILLM实例
openai_llm = OpenAILLM(
    api_key="your-openai-api-key",
    base_url="https://api.openai.com/v1",
    model_name="gpt-4",
    timeout=60
)

# 创建请求
request = OxyRequest(
    messages=[{"role": "user", "content": "你好，你好吗？"}]
)

# 执行请求
response = await openai_llm.execute(request)

# 访问响应
print(response.output)
```


## 注意事项

- `OpenAILLM` 使用官方AsyncOpenAI客户端以获得最佳性能和兼容性
- 该类支持流式和非流式响应
- 启用流式传输时，内容会增量转发给客户端
- 该类在流式传输过程中对思考过程提取有特殊处理：
  - 检测响应中的 `reasoning_content`
  - 自动用 `<think>` 和 `</think>` 标签包装推理内容
  - 实时将思考内容转发到前端
- 配置从多个来源合并，优先级顺序如下：
  1. 请求参数（最高优先级）
  2. 实例特定的LLM参数
  3. 全局LLM配置
- 该类设计用于与所有OpenAI模型和兼容的API一起工作
- 对于流式响应，该类在转发增量更新的同时累积完整响应