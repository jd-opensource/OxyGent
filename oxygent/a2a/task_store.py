from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from .schemas import Task, TaskState


@dataclass
class _Entry:
    task: Task
    created_at: float
    updated_at: float
    canceled: bool = False
    text_buffer: str = ""


class TaskStore:
    def __init__(self, *, ttl_seconds: int = 3600):
        self._ttl_seconds = ttl_seconds
        self._tasks: dict[str, _Entry] = {}

    def _now(self) -> float:
        return time.time()

    def _cleanup(self) -> None:
        if not self._tasks:
            return
        cutoff = self._now() - self._ttl_seconds
        expired = [k for k, v in self._tasks.items() if v.updated_at < cutoff]
        for k in expired:
            self._tasks.pop(k, None)

    def upsert(self, task: Task) -> None:
        self._cleanup()
        now = self._now()
        entry = self._tasks.get(task.id)
        if entry is None:
            self._tasks[task.id] = _Entry(task=task, created_at=now, updated_at=now)
            return
        entry.task = task
        entry.updated_at = now

    def get(self, task_id: str) -> Optional[Task]:
        self._cleanup()
        entry = self._tasks.get(task_id)
        return entry.task if entry else None

    def list(self, *, context_id: Optional[str] = None, limit: int = 100) -> list[Task]:
        self._cleanup()
        tasks = [e.task for e in self._tasks.values()]
        if context_id:
            tasks = [t for t in tasks if t.contextId == context_id]
        tasks.sort(key=lambda t: self._tasks[t.id].updated_at, reverse=True)
        return tasks[: max(1, limit)]

    def mark_canceled(self, task_id: str) -> None:
        entry = self._tasks.get(task_id)
        if entry:
            entry.canceled = True
            entry.task.status.state = TaskState.canceled
            entry.updated_at = self._now()

    def is_canceled(self, task_id: str) -> bool:
        entry = self._tasks.get(task_id)
        return bool(entry and entry.canceled)

    def append_text(self, task_id: str, delta: str) -> None:
        entry = self._tasks.get(task_id)
        if entry is None:
            return
        entry.text_buffer += delta
        entry.updated_at = self._now()
