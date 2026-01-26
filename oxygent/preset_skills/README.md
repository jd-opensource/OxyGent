# OxyGent Skills System

This directory contains preset skills for the OxyGent multi-agent framework. Skills are Markdown-based instructions that extend agent capabilities through prompt injection.

## Available Skills

| Skill | Description |
|-------|-------------|
| `skill-creator` | Create a new skill (directory + SKILL.md) aligned with this runtime |

## Using Skills

Skills are automatically discovered from the following directories:
- `.oxygent/skills/` (project-local)
- `~/.oxygent/skills/` (user-level)
- `oxygent/preset_skills/` (built-in)

And also Claude-style directories (if present):
- `.claude/skills/` (project-local)
- `~/.claude/skills/` (user-level)

To invoke a skill manually, prefix your query with:

```
/<skill-name> [arguments]
```

Example:

```
/skill-creator Create a skill that helps analyze OxyGent logs and suggest fixes.
```

In normal usage, skills can also be auto-activated by the selector based on
the request semantics.

## Creating Custom Skills

### Directory Structure

Create a new directory for your skill:

```
.oxygent/skills/my-skill/
├── SKILL.md          # Required: Main skill file
├── reference.md      # Optional: Detailed documentation
├── examples.md       # Optional: Usage examples
└── scripts/
    └── helper.py     # Optional: Utility scripts
```

### SKILL.md Format

A SKILL.md file consists of YAML frontmatter followed by markdown body:

```yaml
---
name: my-skill
description: A brief description for LLM matching

allowed-tools:
  - file_tools
  - HttpTool


timeout: 120

resources:
  - examples.md
  - template.txt
---

# Skill Title

## Overview
[What this skill does]

## Instructions
[Step-by-step instructions for the agent]

## Examples
[Usage examples]
```

### Frontmatter Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | ✅ | string | Unique skill identifier (lowercase, hyphens) |
| `description` | ✅ | string | Short description for LLM semantic matching |
| `allowed-tools` | ❌ | list/string | Tools available when skill is active |
| `model` | ❌ | string | Preferred LLM model |
| `timeout` | ❌ | number | Timeout override in seconds |
| `resources` | ❌ | list | Additional files to load with skill |

### Best Practices

1. **Naming**: Use lowercase with hyphens (`my-skill`, not `MySkill`)
2. **Description**: Be specific but concise (10-200 characters)
3. **Instructions**: Provide clear, step-by-step guidance
4. **Examples**: Include concrete usage examples
5. **Tools**: Only specify `allowed-tools` if you need to restrict access

### Testing Your Skill

Use the skill testing utilities:

```bash
# Validate a specific skill
python -m oxygent.preset_skills.skill_test_utils

# Or run programmatically
from oxygent.preset_skills.skill_test_utils import SkillValidator
validator = SkillValidator(Path("my-skill/SKILL.md"))
validator.validate()
print(validator.get_report())
```

## Architecture

Skills follow the progressive disclosure pattern:

1. **Startup**: Only metadata (name + description) is loaded
2. **Invocation**: Full content is loaded on-demand
3. **Injection**: Instructions are injected into agent context
4. **Modification**: Environment modifications (tools, model, timeout) are applied

## Contributing

To contribute a new preset skill:

1. Create a new directory under `preset_skills/`
2. Add a `SKILL.md` file following the format above
3. Add optional supporting files (examples, reference docs)
4. Run validation: `python oxygent/preset_skills/skill_test_utils.py`
5. Update this README with your skill

For more detailed guidance, see [AUTHORING_GUIDE.md](AUTHORING_GUIDE.md).
