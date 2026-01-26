"""
Unit tests for the Skills system
"""

import tempfile
from pathlib import Path

import pytest

from oxygent.oxy.skills import (
    SkillContent,
    SkillMetadata,
    SkillRegistry,
    SkillTool,
)
from oxygent.schemas import OxyRequest, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_skill_content():
    """Sample skill markdown content."""
    return """---
name: test-skill
description: A test skill for unit testing
version: "1.0.0"
author: Test Author
---

# Test Skill

This is a test skill that provides instructions for testing.

## Instructions

1. Read the input
2. Process it
3. Return the result
"""


@pytest.fixture
def sample_skill_with_resources():
    """Sample skill with resources."""
    return """---
name: resource-skill
description: A test skill with resources
version: "1.0.0"
resources:
  - examples.md
  - template.txt
---

# Resource Skill

This skill uses additional resource files.
"""


@pytest.fixture
def temp_skill_dir(sample_skill_content, sample_skill_with_resources):
    """Create a temporary directory with skill files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "skills"
        skill_dir.mkdir()

        # Create test skill
        test_skill_dir = skill_dir / "test-skill"
        test_skill_dir.mkdir()
        (test_skill_dir / "SKILL.md").write_text(sample_skill_content)

        # Create resource skill
        resource_skill_dir = skill_dir / "resource-skill"
        resource_skill_dir.mkdir()
        (resource_skill_dir / "SKILL.md").write_text(sample_skill_with_resources)
        (resource_skill_dir / "examples.md").write_text(
            "# Examples\n\nExample 1\nExample 2"
        )
        (resource_skill_dir / "template.txt").write_text("Template content here")

        # Nested SKILL.md under a standard resource directory should NOT be discovered
        nested_skill_dir = resource_skill_dir / "assets" / "nested"
        nested_skill_dir.mkdir(parents=True)
        (nested_skill_dir / "SKILL.md").write_text(
            """---
name: nested-skill
description: This should not be discovered as a skill
---

# Nested
"""
        )

        # Create skill with directory resources
        dir_resource_skill_dir = skill_dir / "dir-resource-skill"
        dir_resource_skill_dir.mkdir()
        (dir_resource_skill_dir / "SKILL.md").write_text(
            """---
name: dir-resource-skill
description: A test skill with directory resources
resources:
  - references/
---

# Dir Resource Skill
"""
        )
        refs = dir_resource_skill_dir / "references"
        refs.mkdir()
        (refs / "workflows.md").write_text("# Workflows\n\nA")
        (refs / "output-patterns.md").write_text("# Output Patterns\n\nB")

        yield skill_dir


@pytest.fixture
def skill_registry(temp_skill_dir):
    """Create a skill registry pointing to temp directory."""
    return SkillRegistry(skill_dirs=[str(temp_skill_dir)], auto_discover=True)


@pytest.fixture
def skill_tool(skill_registry):
    """Create a skill tool with registry."""
    return SkillTool(
        name="Skill", desc="Test Skill tool", skill_registry=skill_registry
    )


@pytest.fixture
def oxy_request():
    """Create a sample oxy request."""
    return OxyRequest(
        arguments={},
        caller="tester",
        caller_category="agent",
        current_trace_id="trace123",
    )


# ──────────────────────────────────────────────────────────────────────────────
# ❷ SkillMetadata Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_skill_metadata_creation():
    """Test creating SkillMetadata directly."""
    metadata = SkillMetadata(
        name="test-skill",
        description="A test skill",
        skill_path=Path("/test/SKILL.md"),
        version="1.0.0",
        author="Test Author",
    )

    assert metadata.name == "test-skill"
    assert metadata.description == "A test skill"
    assert metadata.version == "1.0.0"
    assert metadata.author == "Test Author"


def test_skill_metadata_to_prompt_entry():
    """Test formatting metadata for system prompt."""
    metadata = SkillMetadata(
        name="example-skill",
        description="An example skill for prompt formatting",
        skill_path=Path("/test/SKILL.md"),
    )

    entry = metadata.to_prompt_entry()
    assert entry == "- **example-skill**: An example skill for prompt formatting"


def test_skill_metadata_from_frontmatter():
    """Test creating metadata from frontmatter dict."""
    frontmatter = {
        "name": "test-skill",
        "description": "A test skill",
        "version": "1.0.0",
        "author": "Test Author",
    }

    metadata = SkillMetadata.from_frontmatter(frontmatter, Path("/test/SKILL.md"))

    assert metadata.name == "test-skill"
    assert metadata.description == "A test skill"
    assert metadata.version == "1.0.0"


def test_skill_metadata_missing_required_fields():
    """Test that missing required fields raise ValueError."""
    with pytest.raises(ValueError, match="missing required field: name"):
        SkillMetadata.from_frontmatter({"description": "test"}, Path("/test/SKILL.md"))

    with pytest.raises(ValueError, match="missing required field: description"):
        SkillMetadata.from_frontmatter({"name": "test"}, Path("/test/SKILL.md"))


# ──────────────────────────────────────────────────────────────────────────────
# ❸ SkillContent Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_skill_content_creation():
    """Test creating SkillContent directly."""
    content = SkillContent(
        name="test-skill",
        description="A test skill",
        instructions="Do this, then that",
        allowed_tools=["Read", "Write"],
        model="claude-3-opus",
    )

    assert content.name == "test-skill"
    assert content.instructions == "Do this, then that"
    assert content.allowed_tools == ["Read", "Write"]
    assert content.model == "claude-3-opus"


def test_skill_content_to_context_injection():
    """Test formatting content for context injection."""
    content = SkillContent(
        name="test-skill",
        description="A test skill",
        instructions="Follow these steps:\n1. Read\n2. Write",
    )

    injection = content.to_context_injection()
    assert "[SKILL ACTIVATED: test-skill]" in injection
    assert "Follow these steps:" in injection


def test_skill_content_with_resources():
    """Test context injection includes resources."""
    content = SkillContent(
        name="test-skill",
        description="A test skill",
        instructions="Main instructions",
        resources={"examples.md": "# Examples\n\nExample content"},
    )

    injection = content.to_context_injection()
    assert "## Skill Resources" in injection
    assert "### examples.md" in injection
    assert "# Examples" in injection


def test_skill_content_environment_modifications():
    """Test getting environment modifications."""
    content = SkillContent(
        name="test-skill",
        description="A test skill",
        instructions="Instructions",
        allowed_tools=["Read", "Grep"],
        model="claude-3-opus",
        timeout=300,
    )

    mods = content.get_environment_modifications()
    assert mods["allowed_tools"] == ["Read", "Grep"]
    assert mods["model"] == "claude-3-opus"
    assert mods["timeout"] == 300


def test_skill_content_empty_modifications():
    """Test environment modifications with empty content."""
    content = SkillContent(
        name="test-skill",
        description="A test skill",
        instructions="Instructions",
    )

    mods = content.get_environment_modifications()
    assert mods == {}


def test_skill_content_from_frontmatter_and_body():
    """Test creating content from frontmatter and body."""
    frontmatter = {
        "name": "test-skill",
        "description": "A test skill",
        "version": "1.0.0",
        "allowed-tools": ["Read", "Write"],
    }
    body = "# Instructions\n\nDo this"

    content = SkillContent.from_frontmatter_and_body(
        frontmatter, body, Path("/test/SKILL.md")
    )

    assert content.name == "test-skill"
    assert content.allowed_tools == ["Read", "Write"]
    assert content.instructions == body


def test_skill_content_allowed_tools_string():
    """Test allowed-tools specified as a string."""
    frontmatter = {
        "name": "test-skill",
        "description": "A test skill",
        "allowed-tools": "Read",
    }
    body = "# Instructions\n\nDo this"

    content = SkillContent.from_frontmatter_and_body(
        frontmatter, body, Path("/test/SKILL.md")
    )

    assert content.allowed_tools == ["Read"]


def test_skill_content_allowed_tools_invalid_type():
    """Test allowed-tools specified as a non-list, non-string."""
    frontmatter = {
        "name": "test-skill",
        "description": "A test skill",
        "allowed-tools": 123,
    }
    body = "# Instructions\n\nDo this"

    content = SkillContent.from_frontmatter_and_body(
        frontmatter, body, Path("/test/SKILL.md")
    )

    assert content.allowed_tools == []


# ──────────────────────────────────────────────────────────────────────────────
# ❹ SkillRegistry Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_skill_registry_discovery(temp_skill_dir):
    """Test skill discovery."""
    registry = SkillRegistry(skill_dirs=[str(temp_skill_dir)])

    skills = registry.discover_all()

    assert len(skills) == 3
    assert "test-skill" in skills
    assert "resource-skill" in skills
    assert "dir-resource-skill" in skills


def test_skill_registry_metadata_only(temp_skill_dir):
    """Test that only metadata is loaded during discovery."""
    registry = SkillRegistry(skill_dirs=[str(temp_skill_dir)], auto_discover=True)

    # Metadata should be loaded
    assert "test-skill" in registry.metadata_index
    metadata = registry.metadata_index["test-skill"]
    assert metadata.name == "test-skill"
    assert metadata.description == "A test skill for unit testing"

    # Content cache should be empty
    assert len(registry._content_cache) == 0


def test_skill_registry_load_full_content(skill_registry):
    """Test loading full skill content on-demand."""
    # First load - from disk
    content = skill_registry.load_full_content("test-skill")

    assert content is not None
    assert content.name == "test-skill"
    assert content.version == "1.0.0"
    assert "This is a test skill" in content.instructions

    # Second load - from cache
    content2 = skill_registry.load_full_content("test-skill")
    assert content is content2  # Same object from cache


def test_skill_registry_load_content_with_resources(skill_registry):
    """Test loading skill with resources."""
    content = skill_registry.load_full_content("resource-skill")

    assert content is not None
    assert "examples.md" in content.resources
    assert "template.txt" in content.resources
    assert "# Examples" in content.resources["examples.md"]
    assert "Template content" in content.resources["template.txt"]


def test_skill_registry_load_content_with_directory_resources(skill_registry):
    """Test loading skill with directory resources."""
    content = skill_registry.load_full_content("dir-resource-skill")

    assert content is not None
    assert "references/workflows.md" in content.resources
    assert "references/output-patterns.md" in content.resources
    assert "# Workflows" in content.resources["references/workflows.md"]


def test_skill_registry_resources_string(temp_skill_dir):
    """Test resources specified as a single string."""
    skill_dir = temp_skill_dir / "string-resource-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: string-resource-skill
description: A test skill with string resources
resources: examples.md
---

# Resource Skill
"""
    )
    (skill_dir / "examples.md").write_text("# Examples\n\nExample content")

    registry = SkillRegistry(skill_dirs=[str(temp_skill_dir)])
    content = registry.load_full_content("string-resource-skill")

    assert content is not None
    assert "examples.md" in content.resources


def test_skill_registry_resource_path_traversal(temp_skill_dir):
    """Test that resource paths cannot escape skill directory."""
    (temp_skill_dir / "secret.txt").write_text("secret")

    skill_dir = temp_skill_dir / "traversal-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: traversal-skill
description: A test skill with traversal resource
resources:
  - ../secret.txt
---

# Resource Skill
"""
    )

    registry = SkillRegistry(skill_dirs=[str(temp_skill_dir)])
    content = registry.load_full_content("traversal-skill")

    assert content is not None
    assert "../secret.txt" not in content.resources


def test_skill_registry_nonexistent_skill(skill_registry):
    """Test loading a skill that doesn't exist."""
    content = skill_registry.load_full_content("nonexistent-skill")
    assert content is None


def test_skill_registry_system_prompt_generation(skill_registry):
    """Test generating system prompt section."""
    prompt_section = skill_registry.generate_system_prompt_section()

    assert "## Available Skills" in prompt_section
    assert "**test-skill**" in prompt_section
    assert "**resource-skill**" in prompt_section
    assert "**dir-resource-skill**" in prompt_section
    assert "Do NOT invoke the Skill tool" in prompt_section
    assert "Skill(name=" not in prompt_section


def test_skill_registry_user_help_generation(skill_registry):
    """Test generating user-facing skill help section."""
    help_text = skill_registry.generate_user_help_section()

    assert "Available skills" in help_text
    assert "test-skill" in help_text
    assert "resource-skill" in help_text
    assert "dir-resource-skill" in help_text
    assert "Invoke a skill with" in help_text


def test_skill_registry_empty():
    """Test registry with no skills."""
    registry = SkillRegistry(skill_dirs=["/nonexistent/path"], auto_discover=True)

    assert len(registry) == 0
    prompt = registry.generate_system_prompt_section()
    assert prompt == ""


def test_skill_registry_list_skills(skill_registry):
    """Test listing all skills."""
    skills = skill_registry.list_skills()

    assert len(skills) == 3
    skill_names = {s.name for s in skills}
    assert "test-skill" in skill_names
    assert "resource-skill" in skill_names
    assert "dir-resource-skill" in skill_names


def test_skill_registry_has_skill(skill_registry):
    """Test checking if skill exists."""
    assert skill_registry.has_skill("test-skill")
    assert skill_registry.has_skill("resource-skill")
    assert not skill_registry.has_skill("nonexistent")


def test_skill_registry_clear_cache(skill_registry):
    """Test clearing the content cache."""
    # Load content to populate cache
    skill_registry.load_full_content("test-skill")
    assert len(skill_registry._content_cache) == 1

    # Clear cache
    skill_registry.clear_cache()
    assert len(skill_registry._content_cache) == 0


def test_skill_registry_reload(skill_registry):
    """Test reloading skills."""
    # After initial discovery
    assert len(skill_registry) == 3

    # Modify cache
    skill_registry.load_full_content("test-skill")
    assert len(skill_registry._content_cache) == 1

    # Reload
    skill_registry.reload()
    assert len(skill_registry.metadata_index) == 3
    assert len(skill_registry._content_cache) == 0


# ──────────────────────────────────────────────────────────────────────────────
# ❺ SkillTool Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skill_tool_execute_success(skill_tool, oxy_request):
    """Test successful skill invocation."""
    oxy_request.arguments = {"name": "test-skill", "invocation_source": "user"}

    response = await skill_tool._execute(oxy_request)

    assert response.state == OxyState.COMPLETED
    assert "[SKILL ACTIVATED: test-skill]" in response.output
    assert response.extra["skill_name"] == "test-skill"
    assert response.extra["context_type"] == "skill_injection"


@pytest.mark.asyncio
async def test_skill_tool_execute_missing_name(skill_tool, oxy_request):
    """Test skill invocation without name argument."""
    response = await skill_tool._execute(oxy_request)

    assert response.state == OxyState.FAILED
    assert "Skill name is required" in response.output


@pytest.mark.asyncio
async def test_skill_tool_execute_nonexistent_skill(skill_tool, oxy_request):
    """Test invoking a skill that doesn't exist."""
    oxy_request.arguments = {"name": "nonexistent-skill", "invocation_source": "user"}

    response = await skill_tool._execute(oxy_request)

    assert response.state == OxyState.FAILED
    assert "not found" in response.output


@pytest.mark.asyncio
async def test_skill_tool_execute_with_environment_mods(temp_skill_dir, oxy_request):
    """Test skill with environment modifications."""
    # Create a skill with environment mods
    skill_content = """---
name: env-test-skill
description: A skill with environment mods
allowed-tools:
  - Read
  - Grep

model: claude-3-opus

timeout: 120
---

# Instructions

Use only Read and Grep tools.
"""
    skill_dir = temp_skill_dir / "env-test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(skill_content)

    registry = SkillRegistry(skill_dirs=[str(temp_skill_dir)])
    tool = SkillTool(name="Skill", desc="Test", skill_registry=registry)

    oxy_request.arguments = {"name": "env-test-skill", "invocation_source": "user"}
    response = await tool._execute(oxy_request)

    assert response.state == OxyState.COMPLETED
    env_mods = response.extra["environment_modifications"]
    assert env_mods["allowed_tools"] == ["Read", "Grep"]
    assert env_mods["model"] == "claude-3-opus"
    assert env_mods["timeout"] == 120


def test_skill_tool_set_registry(temp_skill_dir):
    """Test setting registry on tool."""
    tool = SkillTool(name="Skill", desc="Test")
    assert tool.skill_registry is None

    registry = SkillRegistry(skill_dirs=[str(temp_skill_dir)])
    tool.set_registry(registry)

    assert tool.skill_registry is registry


def test_skill_tool_input_schema():
    """Test that input schema is correctly defined."""
    tool = SkillTool(name="Skill", desc="Test")

    assert "name" in tool.input_schema["properties"]
    assert tool.input_schema["properties"]["name"]["type"] == "string"
    assert "arguments" in tool.input_schema["properties"]
    assert "invocation_source" in tool.input_schema["properties"]
    assert "name" in tool.input_schema["required"]


def test_skill_tool_desc_for_llm():
    """Test LLM description generation."""
    tool = SkillTool(name="Skill", desc="Test skill tool")

    desc = tool.desc_for_llm
    assert "Tool: Skill" in desc
    assert "Description: Test skill tool" in desc
    assert "- name: string" in desc


# ──────────────────────────────────────────────────────────────────────────────
# ❻ Integration Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_full_skill_workflow(temp_skill_dir):
    """Test complete workflow from discovery to content loading."""
    # 1. Create registry and discover
    registry = SkillRegistry(skill_dirs=[str(temp_skill_dir)], auto_discover=True)

    # 2. Check discovery worked
    assert len(registry) > 0

    # 3. Generate system prompt
    prompt = registry.generate_system_prompt_section()
    assert "## Available Skills" in prompt

    # 4. Load full content
    for skill_name in registry.metadata_index.keys():
        content = registry.load_full_content(skill_name)
        assert content is not None
        assert content.name == skill_name


@pytest.mark.asyncio
async def test_tool_with_registry_from_request(temp_skill_dir, oxy_request):
    """Test tool using registry from request's mas."""
    registry = SkillRegistry(skill_dirs=[str(temp_skill_dir)], auto_discover=True)

    # Create a mock MAS with skill registry
    class MockMAS:
        skill_registry = registry

    oxy_request.mas = MockMAS()
    oxy_request.current_trace_id = "test-trace"
    oxy_request.node_id = "test-node"

    # Tool without registry set should use MAS registry
    tool = SkillTool(name="Skill", desc="Test")
    oxy_request.arguments = {"name": "test-skill", "invocation_source": "user"}

    response = await tool._execute(oxy_request)

    assert response.state == OxyState.COMPLETED
    assert "[SKILL ACTIVATED: test-skill]" in response.output
