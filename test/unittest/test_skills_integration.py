"""Integration tests for the Skills system.

These tests verify end-to-end skill functionality including:
- MAS initialization with skill registry
- Skill catalog metadata generation
- Skill tool invocation (manual/selector sources)
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oxygent.oxy.llms import MockLLM
from oxygent.oxy.skills import SkillRegistry, SkillTool
from oxygent.schemas import OxyRequest, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def skill_files():
    """Create a temporary directory with test skill files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "skills"
        skill_dir.mkdir()

        # Create a simple test skill
        test_skill_dir = skill_dir / "test-skill"
        test_skill_dir.mkdir()
        (test_skill_dir / "SKILL.md").write_text(
            """---
name: test-skill
description: A test skill for integration testing
version: "1.0.0"
---

# Test Skill

This is a test skill for integration testing.

## Instructions

When activated, this skill provides specific guidance for testing.
Follow these steps:
1. Read the input
2. Process it
3. Return the result
"""
        )

        # Create a skill with environment modifications
        env_skill_dir = skill_dir / "env-skill"
        env_skill_dir.mkdir()
        (env_skill_dir / "SKILL.md").write_text(
            """---
name: env-skill
description: A skill with environment modifications
version: "1.0.0"
allowed-tools:
  - Read
  - Grep

model: claude-3-opus

timeout: 120
---

# Environment Skill

This skill restricts available tools and sets model preferences.

## Instructions

When activated, only use Read and Grep tools.
"""
        )

        # Create a skill with resources
        resource_skill_dir = skill_dir / "resource-skill"
        resource_skill_dir.mkdir()
        (resource_skill_dir / "SKILL.md").write_text(
            """---
name: resource-skill
description: A skill with additional resources
version: "1.0.0"
resources:
  - examples.md
---

# Resource Skill

This skill includes additional resource files.
"""
        )
        (resource_skill_dir / "examples.md").write_text(
            """# Examples

## Example 1
Input: test
Output: processed

## Example 2
Input: demo
Output: verified
"""
        )

        yield skill_dir


@pytest.fixture
def mock_es_client():
    """Create a mock Elasticsearch client."""
    client = MagicMock()
    client.search = MagicMock(return_value={"hits": {"hits": []}})
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = MagicMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_llm():
    """Create a mock LLM that returns simulated responses."""
    llm = MockLLM(
        name="mock_llm",
        desc="Mock LLM for testing",
    )

    # Use object.__setattr__ to bypass Pydantic validation
    response_storage = {"func": None}

    def set_response(func):
        response_storage["func"] = func

    # Override _execute to use custom response
    original_execute = llm._execute

    async def custom_execute(oxy_request):
        if response_storage["func"]:
            return response_storage["func"](oxy_request)
        return await original_execute(oxy_request)

    # Store methods in a way that bypasses Pydantic
    object.__setattr__(llm, "set_response", set_response)
    object.__setattr__(llm, "_execute", custom_execute)

    return llm


@pytest.fixture
def mock_mas(skill_files, mock_es_client, mock_redis_client, mock_llm):
    """Create a mock MAS with skill registry."""
    mas = MagicMock()
    mas.name = "test_mas"
    mas.oxy_name_to_oxy = {}
    mas.es_client = mock_es_client
    mas.redis_client = mock_redis_client
    mas.skill_dirs = [str(skill_files)]
    mas.auto_discover_skills = True

    # Create skill registry
    mas.skill_registry = SkillRegistry(
        skill_dirs=mas.skill_dirs,
        auto_discover=True,
    )

    # Register MockLLM
    mock_llm.set_mas(mas)
    mas.oxy_name_to_oxy["mock_llm"] = mock_llm

    # Create and register Skill tool
    skill_tool = SkillTool()
    skill_tool.set_registry(mas.skill_registry)
    skill_tool.set_mas(mas)
    mas.oxy_name_to_oxy["Skill"] = skill_tool

    # Minimal is_agent (not used in these tests)
    mas.is_agent = lambda name: False

    # Mock get_oxy method
    def get_oxy(name):
        return mas.oxy_name_to_oxy.get(name)

    mas.get_oxy = get_oxy

    return mas


# ──────────────────────────────────────────────────────────────────────────────
# ❷ MAS Integration Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_mas_skill_registry_initialization(skill_files):
    """Test that MAS initializes skill registry correctly."""
    registry = SkillRegistry(skill_dirs=[str(skill_files)], auto_discover=True)

    assert len(registry) == 3
    assert "test-skill" in registry
    assert "env-skill" in registry
    assert "resource-skill" in registry


def test_mas_skill_registry_metadata_only(skill_files):
    """Test that skill registry only loads metadata at startup."""
    registry = SkillRegistry(skill_dirs=[str(skill_files)], auto_discover=True)

    # Metadata should be loaded
    assert "test-skill" in registry.metadata_index
    metadata = registry.metadata_index["test-skill"]
    assert metadata.name == "test-skill"
    assert metadata.description == "A test skill for integration testing"

    # Content cache should be empty initially
    assert len(registry._content_cache) == 0


def test_mas_skill_catalog_generation(skill_files):
    """Test generating skill catalog for system prompt."""
    registry = SkillRegistry(skill_dirs=[str(skill_files)], auto_discover=True)
    catalog = registry.generate_system_prompt_section()

    assert "## Available Skills" in catalog
    assert "**test-skill**" in catalog
    assert "**env-skill**" in catalog
    assert "**resource-skill**" in catalog
    assert "Do NOT invoke the Skill tool" in catalog
    assert "Skill(name=" not in catalog


# ──────────────────────────────────────────────────────────────────────────────
# ❹ Skill Tool Invocation Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skill_tool_invocation(mock_mas):
    """Test invoking a skill through the Skill tool."""
    skill_tool = mock_mas.get_oxy("Skill")

    request = OxyRequest(
        arguments={"name": "test-skill", "invocation_source": "user"},
        caller="test",
        callee="Skill",
        current_trace_id="trace_123",
    )
    request.set_mas(mock_mas)

    response = await skill_tool._execute(request)

    assert response.state == OxyState.COMPLETED
    assert "[SKILL ACTIVATED: test-skill]" in response.output
    assert "Test Skill" in response.output
    assert response.extra["skill_name"] == "test-skill"
    assert response.extra["context_type"] == "skill_injection"


@pytest.mark.asyncio
async def test_skill_tool_with_environment_mods(mock_mas):
    """Test skill invocation with environment modifications."""
    skill_tool = mock_mas.get_oxy("Skill")

    request = OxyRequest(
        arguments={"name": "env-skill", "invocation_source": "user"},
        caller="test",
        callee="Skill",
        current_trace_id="trace_123",
    )
    request.set_mas(mock_mas)

    response = await skill_tool._execute(request)

    assert response.state == OxyState.COMPLETED
    env_mods = response.extra["environment_modifications"]
    assert env_mods["allowed_tools"] == ["Read", "Grep"]
    assert env_mods["model"] == "claude-3-opus"
    assert env_mods["timeout"] == 120


@pytest.mark.asyncio
async def test_skill_tool_with_resources(mock_mas):
    """Test skill invocation with resource files."""
    skill_tool = mock_mas.get_oxy("Skill")

    request = OxyRequest(
        arguments={"name": "resource-skill", "invocation_source": "user"},
        caller="test",
        callee="Skill",
        current_trace_id="trace_123",
    )
    request.set_mas(mock_mas)

    response = await skill_tool._execute(request)

    assert response.state == OxyState.COMPLETED
    assert "## Skill Resources" in response.output
    assert "### examples.md" in response.output
    assert "# Examples" in response.output


@pytest.mark.asyncio
async def test_skill_tool_nonexistent_skill(mock_mas):
    """Test invoking a skill that doesn't exist."""
    skill_tool = mock_mas.get_oxy("Skill")

    request = OxyRequest(
        arguments={"name": "nonexistent", "invocation_source": "user"},
        caller="test",
        callee="Skill",
        current_trace_id="trace_123",
    )
    request.set_mas(mock_mas)

    response = await skill_tool._execute(request)

    assert response.state == OxyState.FAILED
    assert "not found" in response.output


# ──────────────────────────────────────────────────────────────────────────────
# ❼ Edge Case Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_skill_registry_empty_skills():
    """Test skill registry with no skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = SkillRegistry(skill_dirs=[tmpdir], auto_discover=True)
        assert len(registry) == 0
        assert registry.generate_system_prompt_section() == ""


def test_skill_registry_caching(skill_files):
    """Test that content is cached after first load."""
    registry = SkillRegistry(skill_dirs=[str(skill_files)], auto_discover=True)

    # First load - from disk
    content1 = registry.load_full_content("test-skill")
    assert content1 is not None

    # Second load - from cache
    content2 = registry.load_full_content("test-skill")
    assert content1 is content2  # Same object

    # Verify cache has content
    assert "test-skill" in registry._content_cache

    # Clear cache
    registry.clear_cache()
    assert len(registry._content_cache) == 0


def test_skill_integration_placeholder():
    """Placeholder to keep file structure stable."""
    assert True
