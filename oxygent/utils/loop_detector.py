# -*- encoding: utf-8 -*-
"""ReAct loop detection utilities.

Responsibilities:
1. Detect: fingerprint tool calls and spot three loop patterns
   - error_retry: same arguments retried right after an error
   - repeat: same arguments repeated N times in a row
   - repeat_by_output: different arguments but same result category N times
   - cycle: ABAB / ABCABC oscillation between tools
2. Build prompts: pure helpers that turn a detection result into a system
   message the agent layer can inject into its memory.

The detector is stateless aside from a short trace buffer stored in
``shared_data``; it is safe to call once per tool-execution round.

Usage:
    from oxygent.utils.loop_detector import detect_loop, build_loop_break_prompt

    detect_loop(oxy_request.shared_data, tool_calls, tool_results, current_round)
    loop_info = oxy_request.shared_data.get("_loop_detected")
    if loop_info:
        prompt = build_loop_break_prompt(loop_info)
"""

import hashlib
import json
from typing import Optional, Sequence

from oxygent.utils.loop_signatures import (
    compute_signature,
    get_signature_threshold,
    is_benign_signature,
)

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

TRACE_KEY = "_loop_detection_trace"
RESULT_KEY = "_loop_detected"

# Trace buffer length (needs 2*period to detect period-3 cycles)
_MAX_TRACE_LEN = 6

# Error keywords: presence in a tool result marks it as an error
_ERROR_KEYWORDS = (
    "Traceback (most recent call last)",
    "Exception:",
    "Error:",
    "FAILED",
    '"status": "error"',
    '"status": "fail"',
    "<error>",
)

# Signature prefixes that count as errors for _detect_error_retry
_ERROR_SIGNATURE_PREFIXES = (
    "permanent_block",
    "client_error",
    "biz_fail",
    "auth_err",
    "error",
    "denied",
)

# Loop-break prompt templates
_LOOP_BREAK_PROMPTS = {
    "error_retry": (
        "[System] You retried the failing tool '{tool_name}' with the same arguments. "
        "The call will fail again. Analyze the error, change your arguments, "
        "or try a different tool. If the task cannot be completed, say so clearly."
    ),
    "repeat": (
        "[System] You have called '{tool_name}' with identical arguments multiple times. "
        "The result will not change. Stop repeating; switch strategy or give the final answer."
    ),
    "repeat_by_output": (
        "[System] You have called '{tool_name}' with different arguments but the result "
        "category stays the same (signature={output_sig}). Changing arguments will not "
        "unblock this - it is likely a permission / network / policy block, or this "
        "direction has no data. Switch to a different tool or give the final answer."
    ),
    "cycle": (
        "[System] You are oscillating between tools (around '{tool_name}') without progress. "
        "Stop this pattern and give the final answer based on information already gathered."
    ),
}


# ----------------------------------------------------------------------
# Detection entry point
# ----------------------------------------------------------------------


def detect_loop(
    shared_data: dict,
    tool_calls: Sequence,
    tool_results: Sequence,
    current_round: int,
) -> Optional[dict]:
    """Main detection entry point. Call once per ReAct round after tool results are known.

    Args:
        shared_data: Mutable dict shared across the request (``OxyRequest.shared_data``).
        tool_calls: Tool-call dicts for this round, each shaped like
            ``{"tool_name": str, "arguments": dict}``.
        tool_results: Tool execution results aligned with ``tool_calls``. Each item
            can be a plain string, an ``OxyResponse``-like object with an ``output``
            attribute, or any serializable value.
        current_round: Zero-based ReAct round index.

    Returns:
        The detection dict (also stored at ``shared_data[RESULT_KEY]``) when a
        loop is detected, otherwise ``None``.
    """
    if shared_data.get(RESULT_KEY):
        return shared_data[RESULT_KEY]

    trace = shared_data.setdefault(TRACE_KEY, [])

    for tc, result in zip(tool_calls, tool_results):
        tool_name = tc.get("tool_name") or ""
        if not tool_name:
            continue
        arguments = tc.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (ValueError, TypeError):
                arguments = {"__raw__": arguments}

        result_text = _coerce_result_text(result)
        entry = {
            "fingerprint": _compute_fingerprint(tool_name, arguments),
            "output_sig": compute_signature(tool_name, result_text, arguments),
            "tool_name": tool_name,
            "is_error": False,
        }
        entry["is_error"] = _is_error_result(result_text) or _is_error_signature(
            entry["output_sig"]
        )
        trace.append(entry)
        if len(trace) > _MAX_TRACE_LEN:
            trace.pop(0)

    detected = (
        _detect_error_retry(trace)
        or _detect_repeat(trace)
        or _detect_repeat_by_output(trace)
        or _detect_cycle(trace)
    )
    if detected:
        detected["round"] = current_round
        shared_data[RESULT_KEY] = detected
        return detected
    return None


def build_loop_break_prompt(loop_info: dict) -> str:
    """Return a system message describing the detected loop."""
    template = _LOOP_BREAK_PROMPTS.get(
        loop_info.get("type", ""), _LOOP_BREAK_PROMPTS["repeat"]
    )
    return template.format(
        tool_name=loop_info.get("tool_name", "unknown"),
        output_sig=loop_info.get("output_sig", "unknown"),
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _coerce_result_text(result) -> str:
    """Convert a tool result into text for signature / keyword matching."""
    if isinstance(result, str):
        return result
    output = getattr(result, "output", None)
    if output is not None:
        return output if isinstance(output, str) else str(output)
    return str(result)


def _compute_fingerprint(tool_name: str, arguments: dict) -> str:
    """Deterministic 12-char MD5 fingerprint of (tool_name, arguments)."""
    canonical = json.dumps(
        {"t": tool_name, "a": arguments},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.md5(canonical.encode()).hexdigest()[:12]


def _is_error_result(text: str) -> bool:
    return any(kw in text for kw in _ERROR_KEYWORDS)


def _is_error_signature(signature: str) -> bool:
    if not signature:
        return False
    prefix = signature.split(":", 1)[0] if ":" in signature else signature
    return prefix in _ERROR_SIGNATURE_PREFIXES


def _detect_error_retry(trace: list) -> Optional[dict]:
    """Trigger: previous step was an error and current step has the same fingerprint."""
    if len(trace) < 2:
        return None
    prev, curr = trace[-2], trace[-1]
    if prev["is_error"] and curr["fingerprint"] == prev["fingerprint"]:
        return {
            "type": "error_retry",
            "fingerprint": curr["fingerprint"],
            "tool_name": curr["tool_name"],
        }
    return None


def _detect_repeat(trace: list, threshold: int = 3) -> Optional[dict]:
    """Trigger: last ``threshold`` entries share the same fingerprint."""
    if len(trace) < threshold:
        return None
    recent = trace[-threshold:]
    if all(e["fingerprint"] == recent[0]["fingerprint"] for e in recent):
        return {
            "type": "repeat",
            "fingerprint": recent[0]["fingerprint"],
            "tool_name": recent[0]["tool_name"],
        }
    return None


def _detect_repeat_by_output(trace: list) -> Optional[dict]:
    """Trigger: same output signature N times with at least two distinct fingerprints.

    Catches the "LLM changed arguments but the result category stayed the same"
    case. Only fires for classifier-provided signatures (not the ``h:`` fallback)
    and skips benign signatures (``ok``, ``progress``).
    """
    if len(trace) < 2:
        return None
    latest_sig = trace[-1].get("output_sig", "")
    if not latest_sig or latest_sig.startswith("h:"):
        return None
    if is_benign_signature(latest_sig):
        return None
    threshold = get_signature_threshold(latest_sig, default=3)
    if len(trace) < threshold:
        return None
    recent = trace[-threshold:]
    if not all(e.get("output_sig") == latest_sig for e in recent):
        return None
    if len({e.get("fingerprint") for e in recent}) < 2:
        return None
    return {
        "type": "repeat_by_output",
        "output_sig": latest_sig,
        "fingerprint": recent[-1]["fingerprint"],
        "tool_name": recent[-1]["tool_name"],
        "threshold": threshold,
    }


def _detect_cycle(trace: list) -> Optional[dict]:
    """Trigger: period-2 or period-3 oscillation in fingerprints or output signatures."""
    for field, source in (("fingerprint", "input"), ("output_sig", "output")):
        seq = [e.get(field, "") for e in trace]
        for period in (2, 3):
            if len(seq) < period * 2:
                continue
            recent = seq[-(period * 2) :]
            if recent[:period] != recent[period:] or len(set(recent)) <= 1:
                continue
            if source == "output" and all(is_benign_signature(s) for s in recent):
                continue
            return {
                "type": "cycle",
                "source": source,
                "fingerprint": trace[-1]["fingerprint"],
                "output_sig": trace[-1].get("output_sig", ""),
                "tool_name": trace[-1]["tool_name"],
            }
    return None
