# ChatAgent

## 概述

`ChatAgent` 是 OxyGent 框架中的一个会话代理模块，设计用于处理与语言模型的对话交互。它继承自 `LocalAgent` 类，提供了管理会话记忆、处理用户查询和协调语言模型生成响应的功能。


## 功能

`ChatAgent` 是 OxyGent 框架中最基础的会话代理，具有以下关键特性：

1. **会话管理**：维护对话历史，支持多轮对话
2. **提示词配置**：默认提示词为 "You are a helpful assistant."，可以自定义
3. **语言模型交互**：协调与底层语言模型的通信
4. **参数传递**：支持向语言模型传递自定义参数


## ChatAgent能做什么

ChatAgent 适用于以下场景：

1. **简单的问答系统**：构建基础的问答机器人，回答用户查询
2. **客服机器人**：处理常见问题和用户咨询
3. **个人助手**：提供信息查询、简单任务辅助等功能
4. **原型开发和测试**：快速搭建 AI 对话系统原型，验证概念
5. **教育应用**：创建交互式学习助手，辅助教学
6. **作为复杂系统的组件**：作为更大系统中的对话处理模块
7. **内容生成**：生成文本内容，如文案、摘要等


## 为什么使用ChatAgent

1. **简单易用**：作为基础智能体，接口简洁明了，容易上手和集成
2. **灵活性**：支持自定义提示词和参数，可根据需求调整行为
3. **轻量级**：实现简单，没有复杂的逻辑和依赖，运行高效
4. **多轮对话支持**：能够维护对话历史，实现连贯的对话体验
5. **可扩展性**：可以作为其他更复杂智能体的基础组件


## ChatAgent不适合的做什么

1. 需要复杂推理和规划的任务
2. 需要多步骤工作流的应用
3. 需要并行处理多个任务的系统
4. 需要高度自定义行为的智能体

## 方法详解

| 方法                           | 协程（异步）     | 返回值         | 目的（简明）                                                                                                                                                                                   |
| ----------------------------- | ----------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_execute(self, oxy_request)` | 是                | `OxyResponse` | 构建一个临时的对话**记忆**，附加最新的用户查询，合并任何 `llm_params`，并调用配置好的LLM模型；返回包装在 `OxyResponse` 中的模型回复。                                                                 |


## 参数配置

创建 ChatAgent 时可以配置以下参数：

| 参数               | 类型 | 描述           | 默认值                       |
|-------------------|------|--------------|---------------------------|
| `name`            | str  | 智能体名称    | 必填                      |
| `desc`            | str  | 智能体描述    | 必填                      |
| `llm_model`       | str  | 使用的语言模型标识符 | 必填                      |
| `prompt`          | str  | 系统提示词    | "You are a helpful assistant." |
| `short_memory_size` | int  | 短期记忆大小  | 继承自 LocalAgent         |


## 使用示例

```python
from oxygent import MAS, OxySpace
from oxygent.oxy import ChatAgent

# 创建 OxySpace 并注册 ChatAgent
oxy_space = OxySpace()
oxy_space.register_agent(
    ChatAgent(
        name="chat_agent",
        desc="基础聊天智能体",
        llm_model="default_llm",
        prompt="You are a helpful assistant."
    )
)

# 使用 ChatAgent 进行对话
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        result = await mas.chat_with_agent(payload={"query": "你好，请介绍一下自己。"})
        print(result.output)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```


## 相关链接

- [如何和智能体交流](../../../docs/docs_zh/1_1_chat_with_agent.md)
- [选择智能体使用的LLM](../../../docs/docs_zh/1_2_select_llm.md)
- [如何选择智能体](../../../docs/docs_zh/1_4_select_agent.md)