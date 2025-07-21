"""
Unit tests for Message & Memory classes
"""

import pytest
from oxygent.schemas.memory import Message, Memory, Function, ToolCall


# ───────────────────────────────────────────────────────────────────────────────
# Message tests
# ───────────────────────────────────────────────────────────────────────────────
def test_message_factory_shortcuts():
    user = Message.user_message("hi")
    sys = Message.system_message("system")
    ass = Message.assistant_message("ok")
    tool = Message.tool_message("done", name="search", tool_call_id="id1")

    assert user.role == "user" and user.content == "hi"
    assert sys.role == "system"
    assert ass.role == "assistant"
    assert tool.role == "tool" and tool.name == "search"


def test_message_add_overloads():
    """Message + Message / list + Message"""
    m1 = Message.user_message("A")
    m2 = Message.assistant_message("B")

    assert m1 + m2 == [m1, m2]
    assert m1 + [m2] == [m1, m2]
    assert [m2] + m1 == [m2, m1]

    with pytest.raises(TypeError):
        _ = m1 + 1  


def test_message_to_dict_and_tool_calls():
    func = Function(name="foo", arguments='{"x":1}')
    tc = ToolCall(id="1", function=func)
    msg = Message.from_tool_calls([tc], content="payload")

    d = msg.to_dict()
    assert d["role"] == "assistant"
    assert d["tool_calls"][0]["function"]["name"] == "foo"


def test_dict_list_to_messages():
    raw = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {"role": "assistant", "content": "a"},
        {"role": "tool", "content": "will be ignored"},
    ]
    msgs = Message.dict_list_to_messages(raw)
    assert [m.role for m in msgs] == ["system", "user", "assistant"]


# ───────────────────────────────────────────────────────────────────────────────
# Memory tests
# ───────────────────────────────────────────────────────────────────────────────
def test_memory_add_and_recent():
    mem = Memory(max_messages=3)
    for i in range(5):
        mem.add_message(Message.user_message(f"m{i}"))

    recent = mem.to_dict_list()
    assert len(recent) == 3
    assert recent[-1]["content"] == "m4"


def test_memory_add_messages_bulk_and_clear():
    mem = Memory()
    lst = [Message.user_message(f"u{i}") for i in range(3)]
    mem.add_messages(lst)
    assert mem.messages[-1].content == "u2"

    mem.clear()
    assert mem.messages == []


def test_memory_get_recent_n():
    mem = Memory()
    mem.add_messages([Message.user_message(str(i)) for i in range(4)])
    latest_two = mem.get_recent_messages(2)
    assert [m.content for m in latest_two] == ["2", "3"]
