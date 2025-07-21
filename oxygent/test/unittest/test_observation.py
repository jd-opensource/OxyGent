"""
Unit tests for Observation & ExecResult
"""

import pytest

from oxygent.schemas.observation import Observation, ExecResult
from oxygent.schemas.oxy import OxyResponse, OxyState, OxyOutput


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures 
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def monkey_common_utils(monkeypatch):
    monkeypatch.setattr(
        "oxygent.schemas.observation.process_attachments",
        lambda atts: [{"type": "image_url", "image_url": {"url": a}} for a in atts],
        raising=True,
    )
    monkeypatch.setattr(
        "oxygent.schemas.observation.to_json", lambda x: str(x), raising=True
    )


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


def test_to_content_multimodal_false():
    obs = Observation(
        exec_results=[
            ExecResult(
                executor="tool1", oxy_response=make_oxy_resp("plain-result")
            )
        ]
    )
    content = obs.to_content(is_multimodal_supported=False)
    assert isinstance(content, str)
    assert "plain-result" in content


def test_to_content_multimodal_true():
    oxy_out = OxyOutput(result="see img", attachments=["http://img.png"])
    obs = Observation(
        exec_results=[
            ExecResult(
                executor="img_tool", oxy_response=make_oxy_resp(oxy_out)
            )
        ]
    )
    content = obs.to_content(is_multimodal_supported=True)

    assert isinstance(content, list)
    assert content[0]["image_url"]["url"] == "http://img.png"
    assert content[-1]["type"] == "text"
    assert "see img" in content[-1]["text"]
