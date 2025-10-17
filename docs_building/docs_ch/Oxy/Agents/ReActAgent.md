# ReActAgent

ReActAgent 实现了 **ReAct (推理与行动)** 范式，通过在迭代循环中结合语言模型推理和工具执行，实现自主智能体行为。

## 概述

ReActAgent 是 OxyGent 中最通用的智能体，适用于需要多次工具交互的复杂任务。它智能地在以下三个步骤之间交替进行：

1. **推理 (Reasoning)**：使用 LLM 分析任务并决定下一步行动
2. **行动 (Acting)**：基于推理决策执行工具
3. **观察 (Observing)**：处理工具结果以指导下一步推理

这个循环会持续进行，直到智能体得出满意的答案或达到最大迭代次数限制。

## 快速开始

### 基础用法

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

### 使用多个工具

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

## 配置选项

### 核心参数

#### `max_react_rounds` (int, 默认值: 16)

在启动后备机制之前的最大推理-行动迭代次数。

```python
oxy.ReActAgent(
    name="patient_agent",
    max_react_rounds=25,  # 为复杂任务允许更多迭代
    ...
)
```

**何时调整**：

- 对于复杂的多步骤任务，增加此值
- 对于简单任务，减少此值以节省成本
- 通过日志监控实际使用的轮数

#### `llm_model` (str, 必需)

用于推理的 LLM 组件名称。

```python
oxy_space = [
    oxy.HttpLLM(name="fast_model", model_name="gpt-3.5-turbo", ...),
    oxy.HttpLLM(name="smart_model", model_name="gpt-4", ...),
    oxy.ReActAgent(
        name="agent",
        llm_model="smart_model",  # 使用更强大的模型
        ...
    ),
]
```

#### `tools` (list[str])

智能体可以使用的工具名称列表。工具必须在同一个 MAS 中注册。

```python
oxy.ReActAgent(
    name="agent",
    tools=["web_search", "calculator", "file_reader"],
    ...
)
```

### 内存管理

#### `is_discard_react_memory` (bool, 默认值: True)

控制对话历史的存储方式：

- **True**：简单模式 - 仅保留最终的问答对
- **False**：高级模式 - 保留带有权重评分的详细 ReAct 推理步骤

```python
# 简单模式（推荐用于大多数场景）
oxy.ReActAgent(
    name="simple_agent",
    is_discard_react_memory=True,  # 清洁的历史记录
    ...
)

# 高级模式（用于调试或复杂推理链）
oxy.ReActAgent(
    name="detailed_agent",
    is_discard_react_memory=False,  # 保留完整推理轨迹
    memory_max_tokens=30000,
    weight_short_memory=5,
    weight_react_memory=1,
    ...
)
```

#### `memory_max_tokens` (int, 默认值: 24800)

当 `is_discard_react_memory=False` 时用于内存管理的最大 token 数。

```python
oxy.ReActAgent(
    name="agent",
    is_discard_react_memory=False,
    memory_max_tokens=50000,  # 更大的上下文用于详细历史
    ...
)
```

#### `weight_short_memory` (int, 默认值: 5)

选择保留哪些记忆时，短期记忆（最终答案）的优先级权重。

#### `weight_react_memory` (int, 默认值: 1)

ReAct 记忆（中间推理步骤）的优先级权重。

```python
oxy.ReActAgent(
    name="agent",
    weight_short_memory=10,  # 强烈偏好最终答案
    weight_react_memory=1,   # 中间步骤的优先级较低
    ...
)
```

### 高级特性

#### `trust_mode` (bool, 默认值: False)

启用后，允许智能体直接返回工具结果，无需额外推理。

```python
oxy.ReActAgent(
    name="trusted_agent",
    trust_mode=True,  # 可信工具的快速路径
    ...
)
```

**使用场景**：

- 返回格式化结果的数据库查询
- 提供最终答案的 API 调用
- 具有内置结果格式化的工具

**工作原理**：

- 智能体可以在工具调用中包含 `"trust_mode": 1`
- 工具结果立即作为最终答案返回
- 跳过对结果的额外 LLM 推理

#### `prompt` (str, 可选)

自定义系统提示以覆盖默认行为。

```python
custom_prompt = """你是一个专业的数据分析智能体。
你可以使用 SQL 和可视化工具。
在可视化之前始终验证数据。"""

oxy.ReActAgent(
    name="data_agent",
    prompt=custom_prompt,
    tools=["sql_tools", "chart_tools"],
    ...
)
```

#### `func_parse_llm_response` (Callable, 可选)

自定义函数，用于将 LLM 输出解析为结构化响应。

```python
def custom_parser(response: str, request: OxyRequest) -> LLMResponse:
    # 自定义解析逻辑
    if "FINAL:" in response:
        return LLMResponse(
            state=LLMState.ANSWER,
            output=response.split("FINAL:")[-1].strip(),
            ori_response=response
        )
    # ... 工具调用解析逻辑
    return default_parse(response)

oxy.ReActAgent(
    name="agent",
    func_parse_llm_response=custom_parser,
    ...
)
```

#### `func_reflexion` (Callable, 可选)

自定义验证函数，用于检查智能体响应是否可接受。

```python
def custom_reflexion(response: str, request: OxyRequest) -> str:
    """如果响应无效返回错误消息，如果有效返回 None。"""
    if len(response) < 10:
        return "响应太短。请提供更多细节。"
    if "error" in response.lower():
        return "响应包含错误。请重试。"
    return None  # 响应可接受

oxy.ReActAgent(
    name="quality_controlled_agent",
    func_reflexion=custom_reflexion,
    ...
)
```

## 工具检索模式

ReActAgent 支持三种模式来管理大型工具集：

### 模式 1：无检索（所有工具）

无论数量多少，返回所有可用工具。

```python
oxy.ReActAgent(
    name="agent",
    top_k_tools=float('inf'),
    is_retrieve_even_if_tools_scarce=False,
    tools=["tool1", "tool2", "tool3", ...],  # 提供所有工具
)
```

**适用于**：小型工具集（< 20 个工具）

### 模式 2：基于查询的检索

基于查询自动检索前 N 个最相关的工具。

```python
oxy.ReActAgent(
    name="agent",
    top_k_tools=5,  # 每个查询仅提供 5 个最相关的工具
    tools=["tool1", "tool2", ..., "tool100"],
)
```

**适用于**：查询相关性明确的大型工具集

**要求**：在 config.json 中配置 Vearch 向量数据库

### 模式 3：主动获取

提供一个特殊的 "retrieve_tools" 工具，智能体可以调用它来动态搜索相关工具。

```python
oxy.ReActAgent(
    name="agent",
    is_sourcing_tools=True,
    top_k_tools=5,
    tools=["tool1", "tool2", ..., "tool100"],
)
```

**适用于**：初始查询未显示所需工具的复杂任务

**工作原理**：

- 智能体接收有限的初始工具集
- 可以使用搜索查询调用 `retrieve_tools`
- 动态获取其他相关工具

## 理解 ReAct 执行流程

### 正常执行循环

```text
用户查询
    ↓
┌─────────────────────────┐
│  1. 推理 (LLM)          │ ← 系统提示 + 历史 + 查询
│  决定下一步行动          │
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│  2. 行动 (工具调用)      │ ← 执行工具
│  或最终答案              │
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│  3. 观察                │ ← 工具结果
│  添加到 ReAct 记忆      │
└─────────────────────────┘
    ↓
  重复直到得出答案或达到 max_react_rounds
    ↓
最终答案
```

### 后备机制

如果达到 `max_react_rounds` 但未得出最终答案：

1. 从 ReAct 记忆中收集所有工具执行结果
2. 创建摘要："用户问题: {query}\n工具结果: {results}"
3. 使用简化提示进行最终 LLM 调用
4. 返回生成的答案

**后备场景示例**：

```python
# 智能体进行了 16 次工具调用但未形成最终答案
# 后备机制汇总结果：
"""
用户问题：今天的天气和新闻是什么？

工具执行结果：
1. 纽约天气：72°F，晴朗
2. 头条新闻：[文章摘要]
...

请根据这些结果回答。
"""
```

## 响应解析

智能体期望 LLM 响应采用特定格式：

### 工具调用格式

```json
{
  "thought": "我需要检查当前时间",
  "tool_name": "get_current_time",
  "arguments": {"timezone": "UTC"}
}
```

### 多个工具调用

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

### 最终答案格式

不带 JSON 结构的纯文本：

```text
根据搜索结果，asyncio 更适合 I/O 密集型任务，
而多线程更适合 CPU 密集型任务...
```

### Think 标签支持

对于具有思考能力的模型：

```text
<think>
让我逐步分析...
</think>

{"tool_name": "calculator", "arguments": {"x": 5, "y": 3}}
```

智能体会自动在解析前去除 `<think>` 标签。

## 最佳实践

### 1. 选择合适的 max_react_rounds

```python
# 简单的单工具任务
oxy.ReActAgent(name="simple", max_react_rounds=3, ...)

# 多步骤研究任务
oxy.ReActAgent(name="researcher", max_react_rounds=20, ...)

# 复杂推理链
oxy.ReActAgent(name="planner", max_react_rounds=30, ...)
```

### 2. 内存管理策略

```python
# 用于生产聊天机器人（清洁历史）
oxy.ReActAgent(
    name="chatbot",
    is_discard_react_memory=True,
    short_memory_size=10,  # 保留最近 10 次对话
)

# 用于调试/分析（详细轨迹）
oxy.ReActAgent(
    name="debug_agent",
    is_discard_react_memory=False,
    memory_max_tokens=50000,
)
```

### 3. 工具组织

```python
# 对相关工具进行分组
math_agent = oxy.ReActAgent(
    name="math_agent",
    tools=["calculator", "equation_solver", "statistics"],
    ...
)

# 对复杂领域使用层次化智能体
main_agent = oxy.ReActAgent(
    name="main",
    sub_agents=["math_agent", "web_agent", "file_agent"],
    ...
)
```

### 4. 自定义反思以实现质量控制

```python
def domain_validator(response: str, request: OxyRequest) -> str:
    """验证医疗领域的响应。"""
    if not response:
        return "响应不能为空"

    # 领域特定验证
    if "诊断" in response.lower() and "非医生" not in response.lower():
        return "在诊断相关响应中包含医疗免责声明"

    if len(response) < 50:
        return "请提供更详细的医疗信息"

    return None

medical_agent = oxy.ReActAgent(
    name="medical_assistant",
    func_reflexion=domain_validator,
    ...
)
```

### 5. 使用信任模式提高效率

```python
# 返回格式化结果的工具
oxy_space = [
    oxy.HttpLLM(name="llm", ...),
    oxy.FunctionTool(
        name="get_user_info",
        func=lambda user_id: f"用户 {user_id}：张三, zhang@example.com",
        description="获取格式化的用户信息"
    ),
    oxy.ReActAgent(
        name="agent",
        tools=["get_user_info"],
        trust_mode=True,  # 直接返回工具结果
        ...
    ),
]
```

## 常见模式

### 模式 1：研究智能体

```python
research_agent = oxy.ReActAgent(
    name="researcher",
    llm_model="gpt-4",
    tools=["web_search", "summarize", "save_file"],
    max_react_rounds=25,
    is_discard_react_memory=False,  # 保留研究轨迹
    memory_max_tokens=40000,
)
```

### 模式 2：数据分析智能体

```python
analyst = oxy.ReActAgent(
    name="data_analyst",
    llm_model="claude-3-sonnet",
    tools=["sql_tools", "chart_tools", "statistics_tools"],
    max_react_rounds=15,
    trust_mode=True,  # 信任 SQL 查询结果
)
```

### 模式 3：客户支持智能体

```python
support_agent = oxy.ReActAgent(
    name="support",
    llm_model="gpt-3.5-turbo",
    tools=["knowledge_base", "ticket_system", "email_tool"],
    max_react_rounds=8,
    is_discard_react_memory=True,  # 清洁的对话历史
    short_memory_size=20,  # 记住对话上下文
)
```

## API 参考

### 构造函数参数

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `name` | str | 必需 | 智能体的唯一标识符 |
| `is_master` | bool | False | 是否为入口智能体 |
| `llm_model` | str | 必需 | 要使用的 LLM 组件名称 |
| `tools` | list[str] | [] | 工具名称列表 |
| `sub_agents` | list[str] | [] | 子智能体名称列表 |
| `max_react_rounds` | int | 16 | 最大推理-行动迭代次数 |
| `is_discard_react_memory` | bool | True | 丢弃详细的 ReAct 记忆 |
| `memory_max_tokens` | int | 24800 | 记忆的最大 token 数 |
| `weight_short_memory` | int | 5 | 最终答案的优先级权重 |
| `weight_react_memory` | int | 1 | 推理步骤的优先级权重 |
| `trust_mode` | bool | False | 启用直接工具结果返回 |
| `prompt` | str | None | 自定义系统提示 |
| `func_parse_llm_response` | Callable | None | 自定义响应解析器 |
| `func_reflexion` | Callable | None | 自定义验证函数 |
| `top_k_tools` | int | 10 | 要检索的工具数量 |
| `is_sourcing_tools` | bool | False | 启用动态工具检索 |
| `short_memory_size` | int | 10 | 要保留的历史对话数量 |

### 返回类型

**OxyResponse**：标准响应对象

```python
class OxyResponse:
    state: OxyState  # COMPLETED, ERROR 等
    output: str  # 最终答案或错误消息
    extra: dict  # {"react_memory": [...]}
```

**LLMResponse**：解析的 LLM 输出

```python
class LLMResponse:
    state: LLMState  # ANSWER, TOOL_CALL, ERROR_PARSE
    output: str | dict | list  # 取决于状态
    ori_response: str  # 原始 LLM 文本
```

## 其他特性

### 多模态支持

ReActAgent 支持多模态查询（文本、图像、视频）：

```python
result = await mas.call(
    callee="agent",
    arguments={
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这张图片里有什么？"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
                ]
            }
        ]
    }
)
```

### 与流程集成

将 ReActAgent 与高级推理流程结合：

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
