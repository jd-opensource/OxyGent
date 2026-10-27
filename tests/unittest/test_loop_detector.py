# -*- encoding: utf-8 -*-
"""Unit tests for oxygent.utils.loop_detector."""

import pytest

from oxygent.utils.loop_detector import (
    RESULT_KEY,
    TRACE_KEY,
    build_loop_break_prompt,
    detect_loop,
)
from oxygent.utils.loop_signatures import (
    compute_signature,
    is_benign_signature,
    register_signature,
)


def _call(tool_name, **kwargs):
    return {"tool_name": tool_name, "arguments": kwargs}


# ----------------------------------------------------------------------
# detect_loop: _detect_repeat
# ----------------------------------------------------------------------


def test_repeat_triggers_after_three_identical_calls():
    shared = {}
    for i in range(3):
        detect_loop(shared, [_call("search", q="foo")], ["no result"], current_round=i)
    assert shared[RESULT_KEY]["type"] == "repeat"
    assert shared[RESULT_KEY]["tool_name"] == "search"
    assert shared[RESULT_KEY]["round"] == 2


def test_repeat_not_triggered_on_two_calls():
    shared = {}
    for i in range(2):
        detect_loop(shared, [_call("search", q="foo")], ["x"], current_round=i)
    assert RESULT_KEY not in shared


# ----------------------------------------------------------------------
# detect_loop: _detect_error_retry
# ----------------------------------------------------------------------


def test_error_retry_detects_same_args_after_error():
    shared = {}
    detect_loop(shared, [_call("http", url="x")], ["Error: timeout"], current_round=0)
    detect_loop(shared, [_call("http", url="x")], ["Error: timeout"], current_round=1)
    assert shared[RESULT_KEY]["type"] == "error_retry"


def test_error_retry_not_triggered_when_args_change():
    shared = {}
    detect_loop(shared, [_call("http", url="x")], ["Error: timeout"], current_round=0)
    detect_loop(shared, [_call("http", url="y")], ["Error: timeout"], current_round=1)
    assert RESULT_KEY not in shared


# ----------------------------------------------------------------------
# detect_loop: _detect_cycle (ABAB)
# ----------------------------------------------------------------------


def test_cycle_abab_pattern():
    shared = {}
    seq = ["A", "B", "A", "B"]
    for i, name in enumerate(seq):
        detect_loop(shared, [_call(name, q=i % 2)], ["ok"], current_round=i)
    assert shared[RESULT_KEY]["type"] == "cycle"


# ----------------------------------------------------------------------
# detect_loop: _detect_repeat_by_output
# ----------------------------------------------------------------------


def test_repeat_by_output_requires_classifier_signature():
    @register_signature("flaky_tool")
    def _sig(result, args):
        return "biz_fail"

    shared = {}
    # Three different arg sets, same classifier signature.
    for i in range(3):
        detect_loop(
            shared,
            [_call("flaky_tool", attempt=i)],
            [f"attempt {i} failed with code 500"],
            current_round=i,
        )
    assert shared[RESULT_KEY]["type"] == "repeat_by_output"
    assert shared[RESULT_KEY]["output_sig"] == "biz_fail"


def test_benign_signature_does_not_trigger_repeat_by_output():
    @register_signature("good_tool")
    def _sig(result, args):
        return "ok"

    shared = {}
    for i in range(5):
        detect_loop(
            shared,
            [_call("good_tool", attempt=i)],
            [f"success {i}"],
            current_round=i,
        )
    assert RESULT_KEY not in shared


# ----------------------------------------------------------------------
# detect_loop: miscellaneous
# ----------------------------------------------------------------------


def test_detect_loop_is_idempotent_after_hit():
    shared = {}
    for i in range(3):
        detect_loop(shared, [_call("x", a=1)], ["same"], current_round=i)
    first = shared[RESULT_KEY]
    detect_loop(shared, [_call("x", a=1)], ["same"], current_round=99)
    assert shared[RESULT_KEY] is first  # not re-written


def test_detect_loop_handles_oxy_response_like_objects():
    class Fake:
        def __init__(self, text):
            self.output = text

    shared = {}
    for i in range(3):
        detect_loop(shared, [_call("x", a=1)], [Fake("same")], current_round=i)
    assert shared[RESULT_KEY]["type"] == "repeat"


def test_detect_loop_handles_string_arguments():
    shared = {}
    tc = {"tool_name": "x", "arguments": '{"a": 1}'}
    for i in range(3):
        detect_loop(shared, [tc], ["same"], current_round=i)
    assert shared[RESULT_KEY]["type"] == "repeat"


def test_trace_is_bounded():
    shared = {}
    for i in range(20):
        detect_loop(shared, [_call(f"t{i}", a=i)], [f"r{i}"], current_round=i)
    assert len(shared[TRACE_KEY]) <= 6


# ----------------------------------------------------------------------
# Signatures
# ----------------------------------------------------------------------


def test_default_hash_signature_strips_timestamps():
    sig_a = compute_signature("any", "result at 2026-01-01T00:00:00Z done")
    sig_b = compute_signature("any", "result at 2026-07-15T12:30:00Z done")
    assert sig_a == sig_b
    assert sig_a.startswith("h:")


def test_is_benign_signature_matches_prefix():
    assert is_benign_signature("ok")
    assert is_benign_signature("ok:detailed")
    assert not is_benign_signature("biz_fail")


def test_classifier_exception_falls_back_to_hash():
    @register_signature("boom_tool")
    def _sig(result, args):
        raise RuntimeError("classifier broken")

    sig = compute_signature("boom_tool", "payload")
    assert sig.startswith("h:")


# ----------------------------------------------------------------------
# Prompt builder
# ----------------------------------------------------------------------


def test_build_loop_break_prompt_contains_tool_name():
    prompt = build_loop_break_prompt({"type": "repeat", "tool_name": "search"})
    assert "search" in prompt


def test_build_loop_break_prompt_defaults_for_unknown_type():
    prompt = build_loop_break_prompt({"type": "???", "tool_name": "search"})
    assert "search" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
