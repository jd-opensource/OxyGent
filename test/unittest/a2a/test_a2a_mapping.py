import pytest

from oxygent.a2a.mapping import extract_text_from_parts, rest_request_to_oxy_payload
from oxygent.a2a.schemas import Message, MessageSendRequest


def test_extract_text_from_parts_text_only():
    text = extract_text_from_parts([
        {"kind": "text", "text": "hello"},
        {"kind": "text", "text": "world"},
        {"kind": "file", "file": {"uri": "http://example.com"}},
    ])
    assert text == "hello\nworld"


def test_rest_request_to_oxy_payload_ids_and_query():
    req = MessageSendRequest(
        message=Message(
            role="user",
            messageId="m1",
            parts=[{"kind": "text", "text": "hi"}],
        )
    )
    payload, task_id, context_id = rest_request_to_oxy_payload(
        req,
        master_agent_name="master_agent",
    )

    assert payload["query"] == "hi"
    assert payload["request_id"] == "m1"
    assert payload["current_trace_id"] == task_id
    assert payload["group_id"] == context_id
    assert payload["callee"] == "master_agent"
    assert "_a2a" in payload["shared_data"]
