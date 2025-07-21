"""
Unit tests for PydanticOutputParser
"""

import pytest
from pydantic import BaseModel

from oxygent.utils.llm_pydantic_parser import PydanticOutputParser


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Sample Pydantic output schema
# ──────────────────────────────────────────────────────────────────────────────
class Answer(BaseModel):
    text: str
    score: int


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def parser():
    return PydanticOutputParser(output_cls=Answer)


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_get_format_string_no_escape(parser):
    raw_no_escape = parser.get_format_string(escape_json=False)
    raw_escape    = parser.get_format_string(escape_json=True)

    # escape=False 时，双大括号出现次数应 *减少*（但不一定为 0）
    assert raw_no_escape.count("{{") < raw_escape.count("{{")
    assert raw_no_escape.count("}}") < raw_escape.count("}}")

def test_parse_success(parser):
    blob = "Result =>  {\"text\":\"ok\",\"score\":10}"
    obj = parser.parse(blob)
    assert isinstance(obj, Answer)
    assert obj.text == "ok" and obj.score == 10


def test_format_appends_instruction(parser):
    q = "Give answer"
    prompt = parser.format(q)
    assert q in prompt
    assert prompt.endswith(parser.format_string)
