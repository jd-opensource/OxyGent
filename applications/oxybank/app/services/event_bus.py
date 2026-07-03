from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("oxybank.event_bus")


@dataclass
class SampleStatusEvent:
    bank_id: str
    sample_id: str
    old_status: str | None
    new_status: str
    sample_data: dict
    cascade_depth: int = 0
    source: str = "user"


class EventBus:
    """In-process asyncio event bus for sample status changes."""

    def __init__(self, queue_size: int = 10000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._handlers: list = []
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, handler):
        self._handlers.append(handler)

    async def publish(self, event: SampleStatusEvent):
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue full, dropping event for sample %s", event.sample_id)

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("EventBus started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped")

    async def _consume_loop(self):
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                for handler in self._handlers:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error("Event handler error: %s", e, exc_info=True)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
