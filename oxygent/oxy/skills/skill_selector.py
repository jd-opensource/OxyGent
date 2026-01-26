"""Skill selector for semantic (pre-execute) activation.

This module implements a selector-based activation strategy:
- The main agent does not need to call the Skill tool.
- We run an extra lightweight LLM call to choose at most one skill.

The selector only operates on Skill metadata (name + description). Full SKILL.md
content is loaded only after a skill is selected.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from ...schemas import Memory, Message, OxyRequest, OxyResponse, OxyState
from ...utils.common_utils import extract_first_json

from .skill_metadata import SkillMetadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillSelection:
    selected_skill: Optional[str]
    confidence: float
    reason: str


_WORD_RE = re.compile(r"[a-zA-Z0-9_\-]{2,}")


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(text or "")}


def rank_skills_by_keyword_overlap(
    query: str, skills: Iterable[SkillMetadata]
) -> List[SkillMetadata]:
    """Cheap heuristic ranking to reduce selector context size."""

    q = _tokenize(query)
    ranked: list[tuple[int, int, SkillMetadata]] = []
    for s in skills:
        name_toks = _tokenize(s.name)
        desc_toks = _tokenize(s.description)
        score = len(q & (name_toks | desc_toks))
        # Prefer name overlap over description overlap when tied.
        name_score = len(q & name_toks)
        ranked.append((score, name_score, s))
    ranked.sort(key=lambda x: (x[0], x[1], x[2].name), reverse=True)
    return [s for _, __, s in ranked]


def _build_selector_prompt(query: str, skills: List[SkillMetadata]) -> Memory:
    mem = Memory()
    mem.add_message(
        Message.system_message(
            """You are a skill selector.

Choose at most ONE skill from the list.

Return JSON only (no markdown, no prose) using this schema:
{
  "selected_skill": "<name>" | null,
  "confidence": 0.0,
  "reason": "..."
}

Rules:
- Select a skill only if it meaningfully improves execution.
- If none apply, return selected_skill=null with confidence 0.
- Use confidence in [0,1].
"""
        )
    )

    lines = [
        "User request:",
        query.strip(),
        "",
        "Available skills (name: description):",
    ]
    for s in skills:
        lines.append(f"- {s.name}: {s.description}")
    mem.add_message(Message.user_message("\n".join(lines)))
    return mem


def _parse_selector_output(text: str) -> SkillSelection:
    try:
        raw = json.loads(extract_first_json(text))
    except Exception:
        return SkillSelection(
            selected_skill=None,
            confidence=0.0,
            reason="selector_parse_failed",
        )

    selected = raw.get("selected_skill")
    if selected is None:
        selected_skill = None
    elif isinstance(selected, str) and selected.strip():
        selected_skill = selected.strip()
    else:
        selected_skill = None

    confidence = raw.get("confidence", 0.0)
    try:
        confidence_f = float(confidence)
    except Exception:
        confidence_f = 0.0
    if confidence_f < 0:
        confidence_f = 0.0
    if confidence_f > 1:
        confidence_f = 1.0

    reason = raw.get("reason")
    reason_s = reason.strip() if isinstance(reason, str) else ""
    if not reason_s:
        reason_s = "unspecified"

    return SkillSelection(
        selected_skill=selected_skill,
        confidence=confidence_f,
        reason=reason_s,
    )


async def select_skill(
    *,
    oxy_request: OxyRequest,
    llm_model: str,
    skills: List[SkillMetadata],
    query: str,
    max_candidates: int = 30,
    min_confidence: float = 0.6,
) -> SkillSelection:
    """Select a skill for the given query.

    This runs an extra LLM call and expects strict JSON back.
    """

    if not skills:
        return SkillSelection(selected_skill=None, confidence=0.0, reason="no_skills")

    ranked = rank_skills_by_keyword_overlap(query, skills)
    candidates = ranked[: max(1, max_candidates)]
    mem = _build_selector_prompt(query, candidates)

    llm_args = {
        "messages": mem.to_dict_list(),
        "temperature": 0,
    }

    # Avoid streaming selector output to the client.
    resp: OxyResponse = await oxy_request.call(
        callee=llm_model,
        arguments=llm_args,
        is_send_message=False,
        is_save_history=False,
    )

    if resp.state is not OxyState.COMPLETED:
        return SkillSelection(
            selected_skill=None,
            confidence=0.0,
            reason=f"selector_llm_failed:{resp.state}",
        )

    selection = _parse_selector_output(str(resp.output))
    if selection.selected_skill is None:
        return selection

    # Enforce candidate set and threshold.
    if selection.selected_skill not in {s.name for s in candidates}:
        return SkillSelection(
            selected_skill=None,
            confidence=0.0,
            reason="selector_selected_out_of_set",
        )

    if selection.confidence < float(min_confidence):
        return SkillSelection(
            selected_skill=None,
            confidence=selection.confidence,
            reason=f"below_threshold:{selection.reason}",
        )

    return selection
