# A2A（Agent2Agent）协议支持

## 概述

OxyGent 提供一个 **A2A v0.3.0** 的适配层，使 OxyGent MAS 可以作为 **A2A Server** 对外提供标准化接口，便于其他 Agent / 系统通过统一协议与 OxyGent 交互。

- 规范版本：A2A v0.3.0
- 传输方式：HTTP+JSON/REST + SSE（Streaming）
- 实现策略：新增 A2A Adapter（FastAPI Router + 映射 + 内存任务存储），尽量不改动 MAS 核心逻辑

参考规范：<https://a2a-protocol.org/v0.3.0/specification/>

## 主要能力

1. **Agent Card**
   - `GET /.well-known/agent-card.json`

2. **同步消息（REST）**
   - `POST /v1/message:send`

3. **流式消息（SSE）**
   - `POST /v1/message:stream`

4. **任务查询与管理**
   - `GET /v1/tasks/{id}`
   - `GET /v1/tasks`
   - `POST /v1/tasks/{id}:cancel`

## 快速开始（Demo）

### 1）启动 A2A Server Demo

```bash
python3 examples/a2a_server_demo.py
```

启动后你可以访问：

```bash
curl -s http://127.0.0.1:8000/.well-known/agent-card.json | python3 -m json.tool
```

### 2）运行 A2A Client Demo（流式）

```bash
python3 examples/a2a_client_demo.py
```

客户端会：

1. 获取 Agent Card
2. 调用 `message:stream` 并实时打印增量文本
3. 最后调用 `tasks/{id}` 获取任务最终状态

## 请求示例（message:stream）

```json
{
  "message": {
    "kind": "message",
    "messageId": "demo-message",
    "role": "user",
    "parts": [{"kind": "text", "text": "hello"}]
  },
  "configuration": {"blocking": true}
}
```

服务端返回 `text/event-stream`，每个 SSE 的 `data:` 是 JSON 对象，形态可能是：

- `{ "task": <Task> }`
- `{ "artifactUpdate": <TaskArtifactUpdateEvent> }`
- `{ "statusUpdate": <TaskStatusUpdateEvent> }`

## 注意事项（MVP 限制）

- 仅保证 `TextPart(kind="text")` 的输入输出映射；其他 part 类型会被容忍但不会转换为 query。
- 任务存储为进程内内存实现：
  - 建议 demo 使用单进程 worker
  - 断线重连 / resubscribe 不在 MVP 范围
