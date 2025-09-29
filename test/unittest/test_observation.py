"""
Unit tests for Observation & ExecResult
"""

from oxygent.schemas.observation import ExecResult, Observation
from oxygent.schemas.oxy import OxyOutput, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def make_oxy_resp(output):
    return OxyResponse(state=OxyState.COMPLETED, output=output, extra={})


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_add_exec_result_and_to_str():
    obs = Observation()

    obs.add_exec_result(
        ExecResult(executor="search", oxy_response=make_oxy_resp("answer"))
    )

    oxy_out = OxyOutput(result="img_ok", attachments=["http://a.png"])
    obs.add_exec_result(
        ExecResult(executor="vision", oxy_response=make_oxy_resp(oxy_out))
    )

    text = obs.to_str()
    assert "Tool [search] execution result: answer" in text
    assert "Tool [vision] execution result: img_ok" in text
