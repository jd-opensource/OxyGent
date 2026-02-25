import textwrap

import pytest

from oxygent.oxy.skills import SkillRegistry, SkillTool
from oxygent.schemas import OxyRequest, OxyState


class DummyMAS:
    def __init__(self, registry):
        self.skill_registry = registry


def _write_skill(path, *, name: str, description: str, body: str):
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            name: {name}
            description: {description}
            ---

            {body}
            """
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_skill_tool_uses_scoped_skill_dirs_when_provided(tmp_path):
    scoped_root = tmp_path / "scoped"
    global_root = tmp_path / "global"
    _write_skill(
        scoped_root / "a-skill",
        name="a-skill",
        description="from scoped",
        body="Scoped content",
    )
    _write_skill(
        global_root / "b-skill",
        name="b-skill",
        description="from global",
        body="Global content",
    )

    global_registry = SkillRegistry(skill_dirs=[str(global_root)], auto_discover=True)
    mas = DummyMAS(global_registry)

    tool = SkillTool()
    tool.set_mas(mas)
    tool.set_registry(global_registry)

    req = OxyRequest(
        mas=mas,
        arguments={
            "name": "a-skill",
            "invocation_source": "user",
            "skill_dirs": [str(scoped_root.resolve())],
        },
    )
    resp = await tool._execute(req)
    assert resp.state is OxyState.COMPLETED
    assert "[SKILL ACTIVATED: a-skill]" in str(resp.output)


@pytest.mark.asyncio
async def test_skill_tool_without_skill_dirs_uses_default_registry(tmp_path):
    global_root = tmp_path / "global"
    _write_skill(
        global_root / "global-skill",
        name="global-skill",
        description="from global",
        body="Global content",
    )

    global_registry = SkillRegistry(skill_dirs=[str(global_root)], auto_discover=True)
    mas = DummyMAS(global_registry)

    tool = SkillTool()
    tool.set_mas(mas)
    tool.set_registry(global_registry)

    req = OxyRequest(
        mas=mas,
        arguments={
            "name": "global-skill",
            "invocation_source": "user",
        },
    )
    resp = await tool._execute(req)
    assert resp.state is OxyState.COMPLETED
    assert "[SKILL ACTIVATED: global-skill]" in str(resp.output)


@pytest.mark.asyncio
async def test_skill_tool_with_invalid_scoped_dirs_fails(tmp_path):
    global_root = tmp_path / "global"
    _write_skill(
        global_root / "global-skill",
        name="global-skill",
        description="from global",
        body="Global content",
    )

    global_registry = SkillRegistry(skill_dirs=[str(global_root)], auto_discover=True)
    mas = DummyMAS(global_registry)

    tool = SkillTool()
    tool.set_mas(mas)
    tool.set_registry(global_registry)

    req = OxyRequest(
        mas=mas,
        arguments={
            "name": "global-skill",
            "invocation_source": "user",
            "skill_dirs": ["relative/path"],
        },
    )
    resp = await tool._execute(req)
    assert resp.state is OxyState.FAILED
    assert "must be absolute" in str(resp.output)
