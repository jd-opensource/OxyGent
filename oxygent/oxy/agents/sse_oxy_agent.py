import asyncio
import json
import logging

import aiohttp
import httpx
from pydantic import Field

from ...schemas import OxyRequest, OxyResponse, OxyState
from ...utils.common_utils import build_url
from ...utils.sse_utils import iter_sse_events
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

        if self.desc == "":
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    build_url(self.server_url, "/get_description")
                )
                if response.json().get("code") == 200:
                    self.desc = response.json()["data"]["description"]
        self._set_desc_for_llm()

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        logger.info(
            f"Initiating SSE connection. {self.server_url}",
            extra={
                "trace_id": oxy_request.current_trace_id,
                "node_id": oxy_request.node_id,
            },
        )
        payload = oxy_request.model_dump(
            exclude={"mas", "parallel_id", "latest_node_ids", "callee", "callee_category"}
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
        if "shared_data" in payload and "_headers" in payload["shared_data"]:
            del payload["shared_data"]["_headers"]

        url = build_url(self.server_url, "/sse/chat")
        answer = ""

        EXCLUDED_HEADERS = [
            "host",
            "connection",
            "sec-ch-ua",
            "sec-ch-ua-mobile",
            "sec-ch-ua-platform",
            "user-agent",
            "referer",
            "accept-encoding",
            "accept-language",
            "cache-control",
            "sec-fetch-site",
            "sec-fetch-mode",
            "sec-fetch-dest",
            "accept",
            "content-length",
        ]
        headers = {
            k: v
            for k, v in oxy_request.get_shared_data("_headers", {}).items()
            if k.lower() not in EXCLUDED_HEADERS
        }
        headers.update(
            {
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            }
        )

        max_retries = 3
        base_retry_delay = 1.0
        retry_multiplier = 2.0

        retry_count = 0
        last_retry_delay = None

        while retry_count <= max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, data=json.dumps(payload), headers=headers
                    ) as resp:
                        if resp.status != 200:
                            raise aiohttp.ClientResponseError(
                                request_info=resp.request_info,
                                history=resp.history,
                                status=resp.status,
                            )

                        # 使用规范的 SSE 事件解析
                        async for event in iter_sse_events(resp):
                            message_event = event.get("event")
                            message_data = event.get("data")
                            message_id = event.get("id")
                            message_retry = event.get("retry")

                            if message_event == "close":
                                logger.info(
                                    f"Received request to terminate SSE connection: {message_data}. {self.server_url}",
                                    extra={
                                        "trace_id": oxy_request.current_trace_id,
                                        "node_id": oxy_request.node_id,
                                    },
                                )
                                await resp.release()
                                return OxyResponse(
                                    state=OxyState.COMPLETED, output=answer
                                )
                            else:
                                try:
                                    data = json.loads(message_data)
                                    message_data_type = data.get("type", "")
                                    if message_data_type == "answer":
                                        answer = data.get("content")
                                    elif message_data_type in [
                                        "tool_call",
                                        "observation",
                                    ]:
                                        if (
                                            data["content"]["caller_category"] == "user"
                                            or data["content"]["callee_category"]
                                            == "user"
                                        ):
                                            continue
                                        else:
                                            # Discord user and callee
                                            if not self.is_share_call_stack:
                                                data["content"]["call_stack"] = (
                                                    oxy_request.call_stack
                                                    + data["content"]["call_stack"][2:]
                                                )
                                            await oxy_request.send_message(
                                                data,
                                                event=message_event,
                                                id=message_id,
                                                retry=message_retry,
                                            )
                                    else:
                                        await oxy_request.send_message(
                                            data,
                                            event=message_event,
                                            id=message_id,
                                            retry=message_retry,
                                        )
                                except json.JSONDecodeError:
                                    await oxy_request.send_message(
                                        data,
                                        event=message_event,
                                        id=message_id,
                                        retry=message_retry,
                                    )

                        # 如果正常完成，直接返回
                        return OxyResponse(state=OxyState.COMPLETED, output=answer)

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(
                        f"Max retries ({max_retries}) exceeded for SSE connection. {self.server_url}",
                        extra={
                            "trace_id": oxy_request.current_trace_id,
                            "node_id": oxy_request.node_id,
                            "error": str(e),
                        },
                    )
                    return OxyResponse(
                        state=OxyState.FAILED,
                        output=f"SSE connection failed after {max_retries} retries: {str(e)}",
                    )

                if message_retry is not None:
                    retry_delay = message_retry / 1000.0
                elif last_retry_delay is not None:
                    retry_delay = last_retry_delay * retry_multiplier
                else:
                    retry_delay = base_retry_delay

                # 限制最大重试延迟
                retry_delay = min(retry_delay, 30.0)
                last_retry_delay = retry_delay

                logger.warning(
                    f"SSE connection failed, retrying in {retry_delay:.2f} seconds (attempt {retry_count}/{max_retries}). {self.server_url}",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                        "error": str(e),
                    },
                )

                await asyncio.sleep(retry_delay)

            except Exception as e:
                logger.error(
                    f"Unexpected error in SSE connection: {str(e)}",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                    },
                )
                return OxyResponse(
                    state=OxyState.FAILED,
                    output=f"Unexpected error in SSE connection: {str(e)}",
                )
