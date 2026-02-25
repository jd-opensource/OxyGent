import textwrap
from unittest.mock import AsyncMock

import pytest

from oxygent.oxy.agents.skill_agent import SkillAgent
from oxygent.oxy.skills import SkillRegistry, SkillTool
from oxygent.oxy.skills.skill_selector import SkillSelection
from oxygent.oxy.base_tool import BaseTool
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.vearch_client = AsyncMock()
        self.es_client = AsyncMock()
        self.background_tasks = set()
        self.skill_registry = None

    def add_oxy(self, oxy):
        if oxy.name in self.oxy_name_to_oxy:
            raise Exception(f"oxy [{oxy.name}] already exists.")
        self.oxy_name_to_oxy[oxy.name] = oxy

    @staticmethod
    def is_agent(name: str) -> bool:
        return name.startswith("agent_")


class MockLLMTool(BaseTool):
    name: str = "mock_llm"
    desc: str = "Stub LLM"
    category: str = "llm"
    is_multimodal_supported: bool = False

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        return OxyResponse(
            state=OxyState.COMPLETED, output="llm-output", oxy_request=oxy_request
        )


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


@pytest.fixture
def patched_config(monkeypatch):
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_vearch_config",
        lambda: None,
        raising=True,
    )
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_live_prompt_is_active",
        lambda: False,
        raising=True,
    )


@pytest.mark.asyncio
async def test_manual_skill_activation_injects_context_and_rewrites_query(
    patched_config, tmp_path
):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir / "demo-skill",
        name="demo-skill",
        description="demo",
        body="Use this skill. Args: $ARGUMENTS",
    )

    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(skill_dirs=[str(skills_dir)], auto_discover=True)

    agent = SkillAgent(name="agent_master", llm_model="mock_llm", enable_selector=False)
    agent.set_mas(mas)

    skill_tool = SkillTool()
    skill_tool.set_mas(mas)
    skill_tool.set_registry(mas.skill_registry)

    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy["Skill"] = skill_tool
    mas.oxy_name_to_oxy[agent.name] = agent

    req = OxyRequest(
        arguments={"query": "/demo-skill do something"},
        caller="user",
        caller_category="user",
        callee=agent.name,
        callee_category="agent",
        current_trace_id="trace123",
        is_send_message=False,
        is_save_history=False,
    )
    req.mas = mas

    req2 = await agent._before_execute(req)
    assert req2.arguments["query"] == "do something"
    assert "[SKILL ACTIVATED: demo-skill]" in req2.arguments.get("additional_prompt", "")
    assert "Args: do something" in req2.arguments.get("additional_prompt", "")
    assert req2.arguments.get("_skill_activation", {}).get("invocation_source") == "user"


@pytest.mark.asyncio
async def test_selector_activation_invokes_skill_tool(monkeypatch, patched_config, tmp_path):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir / "demo-skill",
        name="demo-skill",
        description="demo",
        body="Selector used.",
    )

    async def _fake_select_skill(**kwargs):
        return SkillSelection(selected_skill="demo-skill", confidence=0.9, reason="ok")

    monkeypatch.setattr(
        "oxygent.oxy.agents.skill_agent.select_skill",
        _fake_select_skill,
        raising=True,
    )

    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(skill_dirs=[str(skills_dir)], auto_discover=True)

    agent = SkillAgent(name="agent_master", llm_model="mock_llm", enable_selector=True)
    agent.set_mas(mas)

    skill_tool = SkillTool()
    skill_tool.set_mas(mas)
    skill_tool.set_registry(mas.skill_registry)

    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy["Skill"] = skill_tool
    mas.oxy_name_to_oxy[agent.name] = agent

    req = OxyRequest(
        arguments={"query": "please help"},
        caller="user",
        caller_category="user",
        callee=agent.name,
        callee_category="agent",
        current_trace_id="trace123",
        is_send_message=False,
        is_save_history=False,
    )
    req.mas = mas

    req2 = await agent._before_execute(req)
    assert "[SKILL ACTIVATED: demo-skill]" in req2.arguments.get("additional_prompt", "")
    assert req2.arguments.get("_skill_activation", {}).get("invocation_source") == "selector"
    assert req2.arguments.get("_skill_selection", {}).get("selected_skill") == "demo-skill"


@pytest.mark.asyncio
async def test_manual_overrides_selector(monkeypatch, patched_config, tmp_path):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir / "demo-skill",
        name="demo-skill",
        description="demo",
        body="Manual.",
    )

    async def _boom(**kwargs):
        raise AssertionError("selector should not run")

    monkeypatch.setattr("oxygent.oxy.agents.skill_agent.select_skill", _boom, raising=True)

    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(skill_dirs=[str(skills_dir)], auto_discover=True)

    agent = SkillAgent(name="agent_master", llm_model="mock_llm", enable_selector=True)
    agent.set_mas(mas)

    skill_tool = SkillTool()
    skill_tool.set_mas(mas)
    skill_tool.set_registry(mas.skill_registry)

    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy["Skill"] = skill_tool
    mas.oxy_name_to_oxy[agent.name] = agent

    req = OxyRequest(
        arguments={"query": "/demo-skill task"},
        caller="user",
        caller_category="user",
        callee=agent.name,
        callee_category="agent",
        current_trace_id="trace123",
        is_send_message=False,
        is_save_history=False,
    )
    req.mas = mas

    req2 = await agent._before_execute(req)
    assert req2.arguments["query"] == "task"
    assert req2.arguments.get("_skill_activation", {}).get("invocation_source") == "user"


@pytest.mark.asyncio
async def test_skill_list_query_returns_metadata_help_without_llm(patched_config, tmp_path):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir / "demo-skill",
        name="demo-skill",
        description="demo",
        body="Body",
    )

    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(skill_dirs=[str(skills_dir)], auto_discover=True)

    agent = SkillAgent(name="agent_master", llm_model="mock_llm", enable_selector=False)
    agent.set_mas(mas)

    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy[agent.name] = agent

    req = OxyRequest(
        arguments={"query": "list skills"},
        caller="user",
        caller_category="user",
        callee=agent.name,
        callee_category="agent",
        current_trace_id="trace123",
        is_send_message=False,
        is_save_history=False,
    )
    req.mas = mas

    req2 = await agent._before_execute(req)
    resp = await agent._execute(req2)
    assert resp.state is OxyState.COMPLETED
    assert "demo-skill" in str(resp.output)


@pytest.mark.asyncio
async def test_skill_list_query_natural_language_alias_returns_metadata_help(patched_config, tmp_path):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir / "demo-skill",
        name="demo-skill",
        description="demo",
        body="Body",
    )

    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(skill_dirs=[str(skills_dir)], auto_discover=True)

    agent = SkillAgent(name="agent_master", llm_model="mock_llm", enable_selector=False)
    agent.set_mas(mas)

    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy[agent.name] = agent

    req = OxyRequest(
        arguments={"query": "what skills do u have?"},
        caller="user",
        caller_category="user",
        callee=agent.name,
        callee_category="agent",
        current_trace_id="trace123",
        is_send_message=False,
        is_save_history=False,
    )
    req.mas = mas

    req2 = await agent._before_execute(req)
    resp = await agent._execute(req2)
    assert resp.state is OxyState.COMPLETED
    assert "demo-skill" in str(resp.output)


@pytest.mark.asyncio
async def test_skill_agent_auto_enables_shell_tools_by_default(patched_config, tmp_path):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir / "demo-skill",
        name="demo-skill",
        description="demo",
        body="Body",
    )

    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(skill_dirs=[str(skills_dir)], auto_discover=True)

    agent = SkillAgent(name="agent_master", llm_model="mock_llm", enable_selector=False)
    agent.set_mas(mas)

    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy[agent.name] = agent

    await agent.init()
    assert "shell_tools" in mas.oxy_name_to_oxy
    assert "run_shell_command" in mas.oxy_name_to_oxy
    assert "run_shell_command" in agent.permitted_tool_name_list


@pytest.mark.asyncio
async def test_skill_agent_scoped_skill_dirs_are_isolated_and_activate_scoped_skill(
    patched_config, tmp_path
):
    skills_a = tmp_path / "skills_a"
    skills_b = tmp_path / "skills_b"
    _write_skill(
        skills_a / "a-skill",
        name="a-skill",
        description="skill in A",
        body="A scope body. Args: $ARGUMENTS",
    )
    _write_skill(
        skills_b / "b-skill",
        name="b-skill",
        description="skill in B",
        body="B scope body.",
    )

    # Global registry intentionally does not contain a-skill.
    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(
        skill_dirs=[str(skills_b)],
        auto_discover=True,
    )

    agent_a = SkillAgent(
        name="agent_a",
        llm_model="mock_llm",
        enable_selector=False,
        skill_dirs=[str(skills_a.resolve())],
    )
    agent_a.set_mas(mas)

    skill_tool = SkillTool()
    skill_tool.set_mas(mas)
    skill_tool.set_registry(mas.skill_registry)

    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy["Skill"] = skill_tool
    mas.oxy_name_to_oxy[agent_a.name] = agent_a

    # Scoped list query must only show A skills.
    req_list = OxyRequest(
        arguments={"query": "list skills"},
        caller="user",
        caller_category="user",
        callee=agent_a.name,
        callee_category="agent",
        current_trace_id="trace123",
        is_send_message=False,
        is_save_history=False,
    )
    req_list.mas = mas
    req_list2 = await agent_a._before_execute(req_list)
    resp_list = await agent_a._execute(req_list2)
    assert "a-skill" in str(resp_list.output)
    assert "b-skill" not in str(resp_list.output)

    # Manual activation of scoped skill succeeds even when global registry cannot resolve it.
    req = OxyRequest(
        arguments={"query": "/a-skill do something"},
        caller="user",
        caller_category="user",
        callee=agent_a.name,
        callee_category="agent",
        current_trace_id="trace124",
        is_send_message=False,
        is_save_history=False,
    )
    req.mas = mas
    req2 = await agent_a._before_execute(req)
    assert req2.arguments["query"] == "do something"
    assert "[SKILL ACTIVATED: a-skill]" in req2.arguments.get("additional_prompt", "")


@pytest.mark.asyncio
async def test_skill_agent_without_skill_dirs_uses_mas_registry(patched_config, tmp_path):
    skills = tmp_path / "skills"
    _write_skill(
        skills / "global-skill",
        name="global-skill",
        description="global",
        body="Global body",
    )

    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(skill_dirs=[str(skills)], auto_discover=True)

    agent = SkillAgent(name="agent_master", llm_model="mock_llm", enable_selector=False)
    agent.set_mas(mas)

    skill_tool = SkillTool()
    skill_tool.set_mas(mas)
    skill_tool.set_registry(mas.skill_registry)

    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy["Skill"] = skill_tool
    mas.oxy_name_to_oxy[agent.name] = agent

    req = OxyRequest(
        arguments={"query": "/global-skill run"},
        caller="user",
        caller_category="user",
        callee=agent.name,
        callee_category="agent",
        current_trace_id="trace125",
        is_send_message=False,
        is_save_history=False,
    )
    req.mas = mas

    req2 = await agent._before_execute(req)
    assert req2.arguments["query"] == "run"
    assert "[SKILL ACTIVATED: global-skill]" in req2.arguments.get(
        "additional_prompt", ""
    )


@pytest.mark.asyncio
async def test_skill_agent_init_fails_when_skill_dirs_not_absolute():
    agent = SkillAgent(
        name="agent_master",
        llm_model="mock_llm",
        enable_selector=False,
        skill_dirs=["relative/skills"],
    )
    with pytest.raises(ValueError, match="must be absolute"):
        await agent.init()


@pytest.mark.asyncio
async def test_skill_agent_init_fails_when_skill_dir_not_exists(tmp_path):
    missing = tmp_path / "not_exists"
    agent = SkillAgent(
        name="agent_master",
        llm_model="mock_llm",
        enable_selector=False,
        skill_dirs=[str(missing.resolve())],
    )
    with pytest.raises(ValueError, match="does not exist"):
        await agent.init()


@pytest.mark.asyncio
async def test_skill_agent_init_allows_scoped_dir_with_no_skills(
    patched_config, tmp_path
):
    empty_dir = tmp_path / "empty_skills_dir"
    empty_dir.mkdir(parents=True)

    mas = DummyMAS()
    mas.skill_registry = SkillRegistry(skill_dirs=[str(empty_dir)], auto_discover=True)

    agent = SkillAgent(
        name="agent_master",
        llm_model="mock_llm",
        enable_selector=False,
        skill_dirs=[str(empty_dir.resolve())],
    )
    agent.set_mas(mas)
    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    mas.oxy_name_to_oxy[agent.name] = agent

    await agent.init()
