import json
import logging

import aiohttp
import httpx
from pydantic import Field

from ...schemas import OxyRequest, OxyResponse, OxyState
from ...utils.common_utils import build_url
from .remote_agent import RemoteAgent

logger = logging.getLogger(__name__)


class SSEOxyGent(RemoteAgent):
    is_share_call_stack: bool = Field(
        True, description="Whether to share the call stack with the agent."
    )

    async def init(self):
        await super().init()

        async with httpx.AsyncClient() as client:
            response = await client.get(build_url(self.server_url, "/get_organization"))
            self.org = response.json()["data"]["organization"]

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        logger.info(
            f"Initiating SSE connection. {self.server_url}",
            extra={
                "trace_id": oxy_request.current_trace_id,
                "node_id": oxy_request.node_id,
            },
        )
        payload = oxy_request.model_dump(
            exclude={"mas", "parallel_id", "latest_node_ids"}
        )
        payload.update(payload["arguments"])
        payload["caller_category"] = "user"
        if self.is_share_call_stack:
            payload["call_stack"] = payload["call_stack"][:-1]
            payload["node_id_stack"] = payload["node_id_stack"][:-1]
        else:
            del payload["call_stack"]
            del payload["node_id_stack"]
            payload["caller"] = "user"
        del payload["arguments"]

        url = build_url(self.server_url, "/sse/chat")
        answer = ""

        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, data=json.dumps(payload), headers=headers
            ) as resp:
                async for line in resp.content:
                    if line:
                        decoded_line = line.decode("utf-8").strip()
                        if decoded_line.startswith("data: "):
                            data = decoded_line[6:]
                            if data == "done":
                                logger.info(
                                    f"Received request to terminate SSE connection: {data}. {self.server_url}",
                                    extra={
                                        "trace_id": oxy_request.current_trace_id,
                                        "node_id": oxy_request.node_id,
                                    },
                                )
                                await resp.release()
                                break
                            data = json.loads(data)

                            if data["type"] == "answer":
                                answer = data.get("content")
                            elif data["type"] in ["tool_call", "observation"]:
                                if (
                                    data["content"]["caller_category"] == "user"
                                    or data["content"]["callee_category"] == "user"
                                ):
                                    continue
                                else:
                                    # Discord user and callee
                                    if not self.is_share_call_stack:
                                        data["content"]["call_stack"] = (
                                            oxy_request.call_stack
                                            + data["content"]["call_stack"][2:]
                                        )
                                    await oxy_request.send_message(data)
                            else:
                                await oxy_request.send_message(data)
        return OxyResponse(state=OxyState.COMPLETED, output=answer)
