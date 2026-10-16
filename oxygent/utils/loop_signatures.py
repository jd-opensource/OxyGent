# -*- encoding: utf-8 -*-
"""Tool-level output signature registry for loop detection.

Design:
    Loop Detector decides whether a tool call is a repeat not only by its input
    fingerprint (hash of tool_name + arguments), but also by an output signature
    that captures "what kind of result did this call produce".

    Two layers:
      - Layer 1 (default fallback): a noise-stripped hash of the result. Catches
        the common case where the LLM varies arguments but keeps producing an
        identical response.
      - Layer 2 (opt-in per tool): tool authors register a classifier function
        via @register_signature. Useful when the raw result contains noise
        (timestamps, UUIDs) or when distinct error categories should be
        collapsed to the same signature (e.g. "permission_denied" vs
        "network_timeout").

    The detector prefers Layer 2 and falls back to Layer 1 when no classifier
    is registered, or if the classifier raises or returns an empty value.

Usage:
    from oxygent.utils.loop_signatures import register_signature

    @register_signature("my_tool")
    def _my_tool_signature(result, args):
        if "PermissionDenied" in result:
            return "denied"
        return "ok"
"""

import hashlib
import re
from typing import Any, Callable, Optional

# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------

_REGISTRY: dict[str, Callable[[Any, dict], str]] = {}


def register_signature(tool_name: str):
    """Decorator that attaches a signature classifier to a tool name.

    Args:
        tool_name: Must match the ``tool_name`` field used in tool calls.
    """

    def decorator(fn: Callable[[Any, dict], str]) -> Callable[[Any, dict], str]:
        _REGISTRY[tool_name] = fn
        return fn

    return decorator


def compute_signature(tool_name: str, result: Any, args: Optional[dict] = None) -> str:
    """Entry point used by the detector.

    Uses the registered classifier when present; otherwise falls back to the
    noise-stripped hash. Classifier exceptions or empty returns fall back too.
    """
    fn = _REGISTRY.get(tool_name)
    if fn is not None:
        try:
            sig = fn(result, args or {})
            if isinstance(sig, str) and sig:
                return sig
        except Exception:
            pass
    return _default_hash_signature(result)


def get_signature_threshold(signature: str, default: int = 3) -> int:
    """Look up the trigger threshold for a signature.

    Supports colon-prefix matching: ``"permanent_block:network_403"`` falls
    back to the ``"permanent_block"`` entry when no exact match exists.
    """
    if signature in _SIGNATURE_THRESHOLDS:
        return _SIGNATURE_THRESHOLDS[signature]
    if ":" in signature:
        prefix = signature.split(":", 1)[0]
        if prefix in _SIGNATURE_THRESHOLDS:
            return _SIGNATURE_THRESHOLDS[prefix]
    return default


# ----------------------------------------------------------------------
# Layer 1: default noise-stripped hash
# ----------------------------------------------------------------------

_NOISE_PATTERNS = [
    # ISO / RFC timestamps
    (
        re.compile(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
        ),
        "<TS>",
    ),
    # UUID
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I
        ),
        "<UUID>",
    ),
    # 32-64 hex strings (trace_id / md5 / sandbox_id)
    (re.compile(r"\b[0-9a-f]{32,64}\b", re.I), "<HEX>"),
    # HTTP Date header
    (
        re.compile(
            r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+GMT"
        ),
        "<HTTPDATE>",
    ),
    # Python object memory addresses
    (re.compile(r"at 0x[0-9a-f]+"), "at 0x<ADDR>"),
    # Keyed trace/request/session ids
    (
        re.compile(
            r"([\"']?[\w-]*(?:trace|request|session|req)[_-]?id[\"']?\s*[:=]\s*)[\"']?[\w.\-]+[\"']?",
            re.I,
        ),
        r"\1<ID>",
    ),
]


def _strip_noise(text: str) -> str:
    for pattern, repl in _NOISE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _default_hash_signature(result: Any) -> str:
    """Layer 1: MD5(first 12 chars) of the noise-stripped result, prefixed ``h:``."""
    text = result if isinstance(result, str) else str(result)
    text = _strip_noise(text)
    return "h:" + hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


# ----------------------------------------------------------------------
# Per-signature thresholds
# ----------------------------------------------------------------------

_SIGNATURE_THRESHOLDS: dict[str, int] = {
    "auth_err": 2,
    "permanent_block": 2,
    "client_error": 3,
    "biz_fail": 3,
    "no_progress": 2,
    "empty": 3,
    "denied": 3,
}


# ----------------------------------------------------------------------
# Benign signatures: never trigger repeat_by_output
# ----------------------------------------------------------------------

BENIGN_SIGNATURES = {"ok", "progress"}


def is_benign_signature(signature: str) -> bool:
    """Return True if the signature represents a successful / progressing call."""
    if signature in BENIGN_SIGNATURES:
        return True
    if ":" in signature:
        prefix = signature.split(":", 1)[0]
        if prefix in BENIGN_SIGNATURES:
            return True
    return False
