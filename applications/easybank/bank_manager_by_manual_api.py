import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class RetrievalRequest(BaseModel):
    query: str
    agent_pin: str
    user_pin: str


@app.post("/user_profile_retrieve")
def user_profile_retrieve(request: RetrievalRequest):
    user_profile_dict = {
        "001": "Arlen, a student, likes music",
        "002": "Tom, a programmer, likes sports",
    }
    portrait = user_profile_dict.get(request.user_pin, "Nothing")
    return f"The current user profile is: {portrait}"


class DepositRequest(BaseModel):
    content: str
    agent_pin: str
    user_pin: str


@app.post("/user_profile_deposit")
def user_profile_deposit(request: DepositRequest):
    print(request.content)
    return "updated user_profile"


@app.get("/list_banks")
def list_banks():
    return [
        {
            "name": "user_profile_retrieve",
            "endpoint": "/user_profile_retrieve",
            "type": "retrieve",
            "description": "A tool for querying user profile",
            "inputSchema": {
                "properties": {
                    "query": {"description": "query", "type": "str"},
                    "agent_pin": {"description": "SystemArg.agent_pin", "type": "str"},
                    "user_pin": {"description": "SystemArg.user_pin", "type": "str"},
                },
                "required": ["query", "agent_pin", "user_pin"],
                "type": "object",
            },
        },
        {
            "name": "user_profile_deposit",
            "endpoint": "/user_profile_deposit",
            "type": "deposit",
            "description": "A tool for updating user profile",
            "inputSchema": {
                "properties": {
                    "content": {"description": "content", "type": "str"},
                    "agent_pin": {"description": "SystemArg.agent_pin", "type": "str"},
                    "user_pin": {"description": "SystemArg.user_pin", "type": "str"},
                },
                "required": ["content", "agent_pin", "user_pin"],
                "type": "object",
            },
        },
    ]


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090)
