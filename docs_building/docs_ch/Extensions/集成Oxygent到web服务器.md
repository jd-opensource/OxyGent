# Integrate Oxygent into Web Server

## 1. Core Objectives
- **Preserve existing FastAPI structure**  
  Maintain the current FastAPI service architecture without changes.
- **Integrate Oxygent's routes and agent capabilities**  
  Incorporate Oxygent's routing and agent functionalities into the existing service.
- **Provide SSE streaming chat interface**  
  Implement a Server-Sent Events (SSE) streaming interface for real-time chat.

## 2. Implementation

### Before Integration
```python
# Original FastAPI startup script
app = FastAPI(
    title="API Server"
)
... 
your other codes
... 

if __name__ == "__main__":
    uvicorn.run(app, host=server_config.host, port=server_config.port)

# Original Oxygent startup script
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(first_query="""please enter question...""", host='0.0.0.0', port=80)

if __name__ == "__main__":
   import asyncio
   asyncio.run(main())
```

### Implementation Details
1. **MAS Initialization**  
   Use `@asynccontextmanager` to manage MAS instances; initialize on startup and clean up resources on shutdown.

2. **Route Integration**  
   Merge Oxygent’s original routes via `app.include_router()`; preserve existing features like static resources and health checks.

3. **Chat Service Migration**  
   Replicate the core chat interface of `sse_chat`; replace self instances with global `global_mas` calls.

### After Integration
```python
from oxygent.routes import router as oxygen_router
from contextlib import asynccontextmanager

# 1. MAS Initialization
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global global_mas
    try:
        # Initialize the MAS instance on startup
        mas = await MAS.create(oxy_space=oxy_space)  
        global_mas = mas
        yield  # Represent it's running
    finally:
        # Clean up resources on shutdown
        if global_mas:
            await global_mas.cleanup_servers()
        global_mas = None

app = FastAPI(
    title="API Server",
    lifespan=lifespan  
)

# 2. Route Integration
app.include_router(oxygen_router)
# Preserve existing routes like static resources and health checks
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 3. Chat Service Migration
@app.api_route("/sse/chat", methods=["GET", "POST"])
async def sse_chat(request: Request):
    # Replace self instances with global global_mas calls
    payload = await request_to_payload(request)
    current_trace_id = payload["current_trace_id"]
    logger.info(
        "SSE connection established.",
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
