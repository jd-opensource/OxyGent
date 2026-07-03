from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.event_bus import EventBus, SampleStatusEvent
from app.storage.es_client import ESClient

logger = logging.getLogger("oxybank.annotation_service")


class AnnotationDispatcher:
    def __init__(
        self,
        max_concurrency: int = 5,
        max_cascade_depth: int = 10,
        agent_timeout: int = 120,
        es_client: ESClient | None = None,
    ):
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_cascade_depth = max_cascade_depth
        self._agent_timeout = agent_timeout
        self._es = es_client
        self._agents: list[dict] = []

    async def load_agents(self) -> None:
        if self._es is None:
            return
        result = self._es.search("agents", query={"term": {"enabled": True}}, size=10000)
        self._agents = result.get("items", [])
        logger.info("Loaded %d annotation agents", len(self._agents))

    async def reload_agents(self) -> None:
        await self.load_agents()

    async def scan_existing_samples(self, agent: dict) -> int:
        """Scan existing samples matching the agent's trigger statuses and dispatch them."""
        if not self._es:
            return 0
        bank_id = agent.get("bank_id", "")
        trigger_statuses = agent.get("trigger_statuses", [])
        if not bank_id or not trigger_statuses:
            return 0

        count = 0
        for status in trigger_statuses:
            query = {"bool": {"filter": [{"term": {"sys_status": status}}]}}
            result = self._es.search(f"samples_{bank_id}", query=query, size=10000)
            items = result.get("items", [])
            for sample in items:
                event = SampleStatusEvent(
                    bank_id=bank_id,
                    sample_id=sample.get("sys_sample_id", sample.get("id", "")),
                    old_status=None,
                    new_status=status,
                    sample_data=sample,
                )
                import asyncio
                asyncio.create_task(self._dispatch_to_agent(agent, event))
                count += 1
        logger.info("Scanned %d existing samples for agent %s", count, agent.get("name", ""))
        return count

    async def handle_status_change(self, event: SampleStatusEvent) -> None:
        if event.cascade_depth >= self._max_cascade_depth:
            logger.warning("Cascade depth %d reached for sample %s; skipping", event.cascade_depth, event.sample_id)
            return
        matching_agents = self._find_matching_agents(event)
        for agent in matching_agents:
            asyncio.create_task(self._dispatch_to_agent(agent, event))

    def _find_matching_agents(self, event: SampleStatusEvent) -> list[dict]:
        matched = []
        for agent in self._agents:
            if agent.get("bank_id") != event.bank_id:
                continue
            if event.new_status in agent.get("trigger_statuses", []):
                matched.append(agent)
        return matched

    async def _dispatch_to_agent(self, agent: dict, event: SampleStatusEvent) -> None:
        async with self._semaphore:
            kind = agent.get("kind", "url")
            if kind == "inline":
                await self._dispatch_inline(agent, event)
            else:
                await self._dispatch_url(agent, event)

    async def _dispatch_url(self, agent: dict, event: SampleStatusEvent) -> None:
        agent_name = agent.get("name", "unknown")
        service_url = agent.get("service_url", "")
        if not service_url:
            self._record_log(event, agent, False, 0, error="No service_url configured")
            return

        payload = dict(event.sample_data) if event.sample_data else {}
        payload.pop("id", None)

        # Ensure all bank schema fields exist in payload (fill missing with "")
        if self._es:
            bank = self._es.get_doc("banks", event.bank_id)
            if bank:
                schema = bank.get("schema", {})
                if isinstance(schema, dict):
                    schema = schema.get("fields", [])
                for f in schema:
                    fname = f.get("name", "")
                    if fname and fname not in payload:
                        payload[fname] = ""

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._agent_timeout) as client:
                resp = await client.post(service_url, json=payload)
                resp.raise_for_status()
                result = resp.json()
            duration_ms = int((time.monotonic() - t0) * 1000)

            output_status = ""
            if result and isinstance(result, dict):
                changes = result.get("changes", result)
                output_status = changes.get("sys_status", "")
                await self._apply_agent_result(event, changes)

            self._record_log(event, agent, True, duration_ms, output_status=output_status)
            logger.info("Agent %s processed sample %s in %dms", agent_name, event.sample_id, duration_ms)

        except httpx.TimeoutException:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._record_log(event, agent, False, duration_ms, error="Timeout")
            logger.error("Agent %s timed out for sample %s", agent_name, event.sample_id)
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._record_log(event, agent, False, duration_ms, error=str(exc))
            logger.error("Agent %s failed for sample %s: %s", agent_name, event.sample_id, exc)

    async def _dispatch_inline(self, agent: dict, event: SampleStatusEvent) -> None:
        """Execute an inline agent's step list against a sample and apply the resulting
        field changes. Steps are a small config-driven DSL — see run_inline_steps for
        the supported step types and interpolation rules."""
        agent_name = agent.get("name", "unknown")
        steps = agent.get("steps", []) or []
        if not steps:
            self._record_log(event, agent, False, 0, error="No steps configured")
            return

        sample = dict(event.sample_data) if event.sample_data else {}
        t0 = time.monotonic()
        try:
            changes = await run_inline_steps(steps, sample)
            duration_ms = int((time.monotonic() - t0) * 1000)
            output_status = changes.get("sys_status", "") if isinstance(changes, dict) else ""
            if changes:
                await self._apply_agent_result(event, changes)
            self._record_log(event, agent, True, duration_ms, output_status=output_status)
            logger.info("Inline agent %s processed sample %s in %dms (changes=%d)",
                        agent_name, event.sample_id, duration_ms, len(changes or {}))
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._record_log(event, agent, False, duration_ms, error=str(exc))
            logger.error("Inline agent %s failed for sample %s: %s", agent_name, event.sample_id, exc)

    def _record_log(self, event: SampleStatusEvent, agent: dict, success: bool, duration_ms: int, output_status: str = "", error: str = ""):
        if not self._es:
            return
        try:
            self._es.index_doc("agent_logs", {
                "bank_id": event.bank_id,
                "agent_id": agent.get("id", ""),
                "agent_name": agent.get("name", ""),
                "sample_id": event.sample_id,
                "input_status": event.new_status,
                "output_status": output_status,
                "success": success,
                "error": error,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning("Failed to record agent log: %s", e)

    async def _apply_agent_result(self, event: SampleStatusEvent, changes: dict) -> None:
        from app.services.sample_service import update_sample
        if not self._es:
            return

        # Auto-snapshot the pre-agent state into sys_prev_* so the annotation UI's
        # "reject" button can restore the previous state. Mirrors what
        # routers/samples.py::update_sample does for human edits — agents used to
        # bypass this because they call the service layer directly.
        #
        # Only fill sys_prev_* the agent didn't explicitly set (so if an
        # advanced user really wants to override, they still can — but the
        # common case doesn't require them to think about these fields at all).
        # Values come from event.sample_data, which is the sample snapshot at
        # dispatch time — exactly the state the "reject" button should return to.
        pre = event.sample_data or {}
        merged = dict(changes)
        merged.setdefault("sys_prev_status", pre.get("sys_status", ""))
        merged.setdefault("sys_prev_template", pre.get("sys_template", ""))
        merged.setdefault("sys_prev_executor", pre.get("sys_executor", ""))

        await update_sample(
            es=self._es,
            bank_id=event.bank_id,
            sample_id=event.sample_id,
            changes=merged,
            user="agent",
            event_bus=None,
            source="agent",
        )

    def set_concurrency(self, n: int) -> None:
        self._max_concurrency = n
        self._semaphore = asyncio.Semaphore(n)


# ---------------------------------------------------------------------------
# Inline agent step runner (module-level, no dispatcher state needed)
# ---------------------------------------------------------------------------
#
# An inline agent is a linear list of steps executed in order against a sample.
# Each step can:
#   - call the configured LLM once (kind: "llm")
#   - assign a sample field to a constant / interpolated value (kind: "set_field")
#   - branch (kind: "if")
#
# Interpolation syntax inside prompts / set_field values:
#   {{sample.<field>}}       → the sample's field at run time (empty string if missing)
#   {{steps.<name>.output}}  → text output of a previously-run named step
#
# Step definitions (JSON):
#   {"type": "llm",       "name": "step1", "prompt": "..."}
#   {"type": "set_field", "field": "sys_status", "value": "Published"}
#   {"type": "if", "when": {"var": "steps.step1.output", "op": "contains", "value": "Ignore"},
#                  "then": [...steps...], "else": [...steps...]}
#
# Supported `when.op`: contains, not_contains, equals, not_equals, starts_with, ends_with

_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")


def _resolve_var(path: str, ctx: dict) -> str:
    """Resolve dotted paths like 'sample.query' or 'steps.foo.output' against ctx."""
    parts = path.split(".")
    cur: Any = ctx
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p, "")
        else:
            return ""
        if cur is None:
            return ""
    return str(cur) if cur is not None else ""


def _interpolate(template: str, ctx: dict) -> str:
    """Replace every {{path}} in `template` with the resolved value from ctx."""
    if not template:
        return ""
    if not isinstance(template, str):
        return str(template)

    def repl(m: re.Match) -> str:
        return _resolve_var(m.group(1), ctx)

    return _VAR_PATTERN.sub(repl, template)


def _eval_when(cond: dict, ctx: dict) -> bool:
    """Evaluate a single-operator condition against ctx.
    Missing / malformed conditions default to False so bad configs fail closed."""
    if not isinstance(cond, dict):
        return False
    var_path = cond.get("var", "")
    op = cond.get("op", "equals")
    expected = cond.get("value", "")
    actual = _resolve_var(var_path, ctx) if var_path else ""
    expected_s = str(expected) if expected is not None else ""
    if op == "contains":       return expected_s in actual
    if op == "not_contains":   return expected_s not in actual
    if op == "equals":         return actual == expected_s
    if op == "not_equals":     return actual != expected_s
    if op == "starts_with":    return actual.startswith(expected_s)
    if op == "ends_with":      return actual.endswith(expected_s)
    return False


async def _call_llm(prompt: str) -> str:
    """Call the configured LLM once and return the plain text output.
    Uses the same base_url/api_key/model as the template designer (config.llm).
    Non-streaming — inline agents are just sequential text ops, streaming would
    only add complexity here."""
    from app.config import get_config
    cfg = get_config().llm
    url = cfg.base_url.rstrip("/")
    if "/chat/completions" not in url:
        url += "/chat/completions"
    payload = {
        "model": cfg.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.api_key}",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


async def run_inline_steps(steps: list, sample: dict) -> dict:
    """Execute the given step list against a sample and return the accumulated
    field changes as a plain dict (suitable for feeding into sample_service.update_sample).

    The runner mutates neither the input sample nor the input steps. It builds a
    context of the form {"sample": <sample dict>, "steps": {"name1": {"output": "..."}}}
    used for {{...}} interpolation and if-condition evaluation.
    """
    ctx: dict[str, Any] = {"sample": dict(sample), "steps": {}}
    changes: dict[str, Any] = {}

    async def run(step_list: list) -> None:
        for step in step_list or []:
            if not isinstance(step, dict):
                continue
            t = step.get("type", "")
            if t == "llm":
                prompt = _interpolate(step.get("prompt", ""), ctx)
                output = await _call_llm(prompt)
                name = step.get("name", "")
                if name:
                    ctx["steps"][name] = {"output": output}
            elif t == "set_field":
                field = step.get("field", "")
                if not field:
                    continue
                raw_value = step.get("value", "")
                # Interpolate string values; pass through non-string literals unchanged
                # so integer/boolean priorities and the like survive.
                if isinstance(raw_value, str):
                    value = _interpolate(raw_value, ctx)
                else:
                    value = raw_value
                changes[field] = value
                # Also update ctx.sample so later steps see the new value via {{sample.field}}
                ctx["sample"][field] = value
            elif t == "if":
                branch = step.get("then", []) if _eval_when(step.get("when", {}), ctx) else step.get("else", [])
                await run(branch)
            else:
                logger.warning("Unknown inline step type: %r — skipping", t)

    await run(steps)
    return changes
