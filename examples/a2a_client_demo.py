import asyncio
import json
import os

import httpx


def _new_message_request(text: str):
    return {
        "message": {
            "kind": "message",
            "messageId": "demo-message",
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
        },
        "configuration": {"blocking": True},
    }


async def main():
    base = os.getenv("A2A_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    async with httpx.AsyncClient(timeout=None) as client:
        card = (await client.get(f"{base}/.well-known/agent-card.json")).json()
        print("AgentCard.url:", card.get("url"))

        req = _new_message_request("hello from a2a client")

        task_id = None
        try:
            async with client.stream(
                "POST",
                f"{base}/v1/message:stream",
                json=req,
                headers={"accept": "text/event-stream"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    payload = json.loads(line[5:].strip())
                    if "task" in payload and task_id is None:
                        task_id = payload["task"]["id"]
                        print("taskId:", task_id)
                    if "artifactUpdate" in payload:
                        parts = payload["artifactUpdate"]["artifact"]["parts"]
                        if parts and parts[0].get("kind") == "text":
                            print(parts[0].get("text", ""), end="", flush=True)
                    if "statusUpdate" in payload and payload["statusUpdate"].get("final"):
                        print("\nfinal state:", payload["statusUpdate"]["status"]["state"])
                        break
        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.HTTPError) as e:
            print(f"\nstream error: {type(e).__name__}: {e}")

        if task_id:
            task = (await client.get(f"{base}/v1/tasks/{task_id}")).json()
            print("tasks/get:", task.get("status", {}).get("state"))


if __name__ == "__main__":
    asyncio.run(main())
