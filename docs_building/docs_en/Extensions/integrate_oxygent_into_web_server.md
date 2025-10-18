# 集成Oxygent到web服务器

## 1. 核心目标
- **保留现有FastAPI服务架构**  
  保持当前的FastAPI服务架构不变。
- **集成Oxygent的路由和Agent能力**  
  将Oxygent的路由和Agent功能集成到现有服务中。
- **提供SSE长连接对话接口**  
  实现Server-Sent Events (SSE) 长连接接口，支持实时对话功能。

## 2. 改造实现

### 集成前代码
```python
# 原始FastAPI启动脚本
app = FastAPI(
    title="API Server"
)
... 
其他代码
... 

if __name__ == "__main__":
    uvicorn.run(app, host=server_config.host, port=server_config.port)

# 原始Oxygent启动脚本
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="""请输入问题...""", host='0.0.0.0', port=80)

if __name__ == "__main__":
   import asyncio
   asyncio.run(main())
```

### 实现细节
1. **MAS初始化**  
   使用 `@asynccontextmanager` 管理 MAS 实例；在启动时初始化并在关闭时清理资源。

2. **路由集成**  
   通过 `app.include_router()` 合并 Oxygent 的原始路由；保留静态资源和健康检查等现有功能。

3. **聊天服务迁移**  
   复制 `sse_chat` 的核心聊天接口；将 self 实例替换为全局的 `global_mas` 调用。

### 集成后代码
```python
from oxygent.routes import router as oxygen_router
from contextlib import asynccontextmanager

# 1. MAS初始化
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global global_mas
    try:
        # 在启动时初始化MAS实例
        mas = await MAS.create(oxy_space=oxy_space)  
        global_mas = mas
        yield  # 表示正在运行
    finally:
        # 在关闭时清理资源
        if global_mas:
            await global_mas.cleanup_servers()
        global_mas = None

app = FastAPI(
    title="API Server",
    lifespan=lifespan  
)

# 2. 路由集成
app.include_router(oxygen_router)
# 保留静态资源和健康检查等现有路由
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 3. 聊天服务迁移
@app.api_route("/sse/chat", methods=["GET", "POST"])
async def sse_chat(request: Request):
    # 将self实例替换为全局的global_mas调用
    payload = await request_to_payload(request)
    current_trace_id = payload["current_trace_id"]
    logger.info(
        "SSE连接已建立。",
        extra={"trace_id": current_trace_id},
    )
    redis_key = f"{global_mas.message_prefix}:{global_mas.name}:{current_trace_id}"
    task = asyncio.create_task(
        global_mas.chat_with_agent(payload=payload, send_msg_key=redis_key)
    )
    return EventSourceResponse(
        self.event_stream(redis_key, current_trace_id, task)
    )

if __name__ == "__main__":
    uvicorn.run(app, host=server_config.host, port=server_config.port)
```
