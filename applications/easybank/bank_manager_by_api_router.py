import uvicorn
from fastapi import APIRouter, Body, FastAPI
from fastapi.routing import APIRoute

app = FastAPI()
router = APIRouter(tags=["bank"])


@router.post("/user_profile_retrieve", description="A tool for querying user profile")
def user_profile_retrieve(
    query: str = Body(description="query"),
    user_pin: str = Body(description="SystemArg.user_pin"),
    agent_pin: str = Body(description="SystemArg.agent_pin"),
):
    user_profile_dict = {
        "001": "Arlen, a student, likes music",
        "002": "Tom, a programmer, likes sports",
    }
    portrait = user_profile_dict.get(user_pin, "Nothing")
    return f"The current user profile is: {portrait}"


@router.post("/user_profile_deposit", description="A tool for updating user profile")
def user_profile_deposit(
    content: str = Body(description="content"),
    user_pin: str = Body(description="SystemArg.user_pin"),
    agent_pin: str = Body(description="SystemArg.agent_pin"),
) -> str:
    print(agent_pin, user_pin, content)
    return "updated user_profile"


app.include_router(router)


@app.get("/list_banks")
def list_banks():
    return get_banks_from_router(router)


def get_banks_from_router(router: APIRouter):
    banks = []
    for route in router.routes:
        if isinstance(route, APIRoute) and "bank" in getattr(route, "tags", []):
            description = route.description
            input_schema = {"type": "object", "properties": {}, "required": []}
            for param in route.dependant.query_params + route.dependant.body_params:
                param_type = param.type_
                # Type conversion (simple implementation)
                if param_type is str:
                    t = "string"
                elif param_type is int:
                    t = "integer"
                elif param_type is float:
                    t = "number"
                elif param_type is bool:
                    t = "boolean"
                else:
                    t = "string"
                input_schema["properties"][param.name] = {
                    "type": t,
                    "description": param.field_info.description or "",
                }
                if param.required:
                    input_schema["required"].append(param.name)
            banks.append(
                {
                    "name": route.endpoint.__name__,
                    "endpoint": route.path,
                    "methods": route.methods,
                    "description": description,
                    "inputSchema": input_schema,
                }
            )
    return banks


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090)
