# Skill Authoring Guide

This guide provides comprehensive instructions for creating high-quality skills for the OxyGent framework.

## Table of Contents

1. [Understanding Skills](#understanding-skills)
2. [Skill File Format](#skill-file-format)
3. [Writing Effective Instructions](#writing-effective-instructions)
4. [Environment Modifications](#environment-modifications)
5. [Skill Patterns](#skill-patterns)
6. [Testing and Validation](#testing-and-validation)
7. [Examples and Templates](#examples-and-templates)

---

## Understanding Skills

### What are Skills?

Skills are **Markdown-based instructions** that extend agent capabilities. Unlike tools (which execute code), skills are **interpreted by the LLM** to guide behavior.

### Skills vs Tools

| Aspect | Skills | Tools |
|--------|--------|-------|
| Definition | Markdown instructions | Python/API code |
| Execution | LLM interprets instructions | Code executes directly |
| Flexibility | High (natural language) | Low (structured) |
| Speed | Slower (LLM reasoning) | Faster (direct execution) |
| Best For | Complex workflows, guidance | Deterministic operations |

### When to Create a Skill

Create a skill when:
- The task requires multi-step reasoning
- The workflow benefits from natural language guidance
- You want to provide context-specific instructions
- The task doesn't require exact, deterministic output

Create a tool when:
- The task requires exact computation
- You need reliable, repeatable results
- Performance is critical
- The operation is simple and well-defined

---

## Skill File Format

### Basic Structure

```markdown
---
name: skill-name
description: A clear, concise description
---

# Skill Title

## Overview
[What this skill does]

## Instructions
[Step-by-step guidance]

## Examples
[Concrete examples]
```

### Frontmatter Reference

#### Required Fields

**`name`** (string): Unique identifier
- Must be lowercase
- Use hyphens for multi-word names
- Must match directory name
- Example: `skill-creator`

**`description`** (string): Semantic matching text
- 10-200 characters recommended
- Describes what the skill does
- Used by LLM to decide when to invoke
- Example: "Create a new skill skeleton and SKILL.md"

#### Optional Fields

**`allowed-tools`** (list | string): Tool restriction
- List of tool names the agent can use
- Single string also accepted
- Omit to allow all tools
- Example: `["file_tools", "HttpTool"]`

**`model`** (string): Preferred LLM model
- Specify model for best results
- Useful for skills requiring advanced reasoning
- Example: `"claude-3-opus"`

**`timeout`** (number): Timeout override
- In seconds
- Useful for long-running operations
- Example: `180` (3 minutes)

**`resources`** (list): Additional files
- Filenames relative to skill directory
- Loaded with skill content
- Example: `["examples.md", "template.md"]`

---

## Writing Effective Instructions

### Principles

1. **Be Specific**: Tell the agent exactly what to do
2. **Be Sequential**: Number steps in execution order
3. **Provide Context**: Explain why steps matter
4. **Include Examples**: Show expected input/output
5. **Handle Edge Cases**: Tell the agent what to do in unusual situations

### Step-by-Step Template

```markdown
### Step 1: [Action Name]

**Objective:** [What this step accomplishes]

**Actions:**
1. [Sub-action 1]
2. [Sub-action 2]

**Expected Output:** [What to produce]

**Example:**
\`\`\`
[Concrete example]
\`\`\`
```

### Writing for Different Skill Types

#### Analysis Skills

For skills that analyze content:

1. **Define the analysis framework**
   - What categories to examine
   - What to look for in each category

2. **Provide evaluation criteria**
   - How to judge quality
   - What constitutes issues vs. acceptable

3. **Specify output format**
   - Use templates for consistency
   - Include severity levels

Example:
```markdown
## Analysis Categories

### Security (Critical)
- SQL injection
- XSS vulnerabilities
- Authentication flaws

### Code Quality (High)
- Cyclomatic complexity
- Naming conventions
- Documentation

## Output Format

### Critical Issues
- [ ] Issue: [description]
  - File: [path:line]
  - Risk: High/Medium/Low
  - Fix: [recommendation]
```

#### Creative Skills

For skills that generate content:

1. **Understand requirements first**
   - Ask clarifying questions
   - Identify audience and purpose

2. **Provide structure templates**
   - Give the agent a format to follow
   - Include section requirements

3. **Include style guidelines**
   - Tone and voice
   - Formatting conventions

Example:
```markdown
### Step 1: Gather Requirements

**Ask the user:**
- What type of document?
- Who is the audience?
- What depth of detail?

### Step 2: Choose Template

**For API Docs:**
[Template structure]

**For Tutorials:**
[Template structure]
```

#### Research Skills

For skills that gather information from a provided URL:

1. **Define search strategy**
   - Where to look first
   - How to evaluate sources

2. **Synthesis approach**
   - How to combine multiple sources
   - How to handle contradictions

3. **Citation guidelines**
   - How to attribute sources
   - What level of detail

Example:
```markdown
### Source Credibility

**High Credibility:**
- Official documentation
- Peer-reviewed papers
- Reputable news

**Medium Credibility:**
- Technical blogs by known experts
- Industry publications

**Low Credibility (verify):**
- Forums and social media
```

---

## Environment Modifications

### Tool Restrictions

Use `allowed-tools` to restrict what tools the agent can use:

```yaml
---
allowed-tools:
  - file_tools
  - HttpTool
---
```

**When to use:**
- Security-sensitive operations (read-only access)
- Preventing unintended side effects
- Enforcing specific workflows

**When NOT to use:**
- The skill needs full flexibility
- You're not sure what tools might be needed

### Model Selection

Use `model` to specify the best model for the skill:

```yaml
---

---
```

**Recommendations:**
- Use `claude-3-opus` for complex reasoning
- Use `claude-3-sonnet` for balanced performance
- Omit for default model selection

### Timeout

Use `timeout` for long-running operations:

```yaml
---
timeout: 300  # 5 minutes
---
```

**Use cases:**
- Research that requires multiple web requests
- Large document processing
- Complex analysis tasks

---

## Skill Patterns

### Pattern 1: Checklist Skill

For skills that verify compliance with rules:

```markdown
### Step 1: Read the Content

### Step 2: Check Each Item

| Item | Status | Notes |
|------|--------|-------|
| [Rule 1] | ☐ | |
| [Rule 2] | ☐ | |

### Step 3: Generate Report

[Report template]
```

### Pattern 2: Transformation Skill

For skills that convert one format to another:

```markdown
### Input Format
[Description of expected input]

### Output Format
[Description of output]

### Transformation Rules

1. [Rule 1]
2. [Rule 2]

### Example

**Input:**
\`\`\`
[input example]
\`\`\`

**Output:**
\`\`\`
[output example]
\`\`\`
```

### Pattern 3: Decision Tree Skill

For skills with branching logic:

```markdown
### Decision Point 1: [Condition]

**If [condition A]:**
- Follow [procedure A]

**If [condition B]:**
- Follow [procedure B]

**Else:**
- Follow [default procedure]
```

### Pattern 4: Template-Based Skill

For skills that fill in templates:

```markdown
### Output Template

\`\`\`
# [Title]

## Overview
[Generated from input]

## Details
[Generated from analysis]
\`\`\`

### Filling Instructions

- **[Title]**: Derive from [source]
- **[Overview]**: Summarize [content]
- **[Details]**: Extract [specifics]
```

---

## Testing and Validation

### Local Validation

Use the skill testing utilities:

```python
from oxygent.preset_skills.skill_test_utils import SkillValidator

validator = SkillValidator(Path("my-skill/SKILL.md"))
if validator.validate():
    print("✅ Skill is valid!")
else:
    print("❌ Validation failed:")
    print(validator.get_report())
```

### Manual Testing

Test your skill with the ReActAgent:

```python
from oxygent import MAS

async def test_skill():
    mas = MAS()
    await mas.__aenter__()

    # Create an agent with skill support
    agent = ReActAgent(
        name="test-agent",
        llm_model="your-model",
        enable_skills=True,
    )
    agent.set_mas(mas)

    # Test the skill
    response = await agent.arun(
        "/skill-creator Create a new skill named my-skill (local .oxygent/skills/)"
    )
    print(response.output)
```

### Common Issues

**Skill not being invoked:**
- Check description is clear and specific
- Verify skill is in the correct directory
- Check that MAS initialization completed successfully

**Instructions not being followed:**
- Make steps more explicit
- Add examples
- Break complex steps into smaller ones

**Context bloat:**
- Move reference material to separate resource files
- Use progressive disclosure (main SKILL.md for overview)
- Lazy-load resources only when needed

---

## Examples and Templates

### Minimal Skill Template

```markdown
---
name: minimal-skill
description: A minimal skill template
---

# Minimal Skill

## Overview
This skill does one thing well.

## Instructions

1. Do step one
2. Do step two
3. Return result

## Examples

**Input:** Example input
**Output:** Example output
```

### Advanced Skill Template

```markdown
---
name: advanced-skill
description: A comprehensive skill with all features

allowed-tools:
  - file_tools
  - HttpTool


timeout: 180

resources:
  - examples.md
  - reference.md
---

# Advanced Skill

## Overview
[Comprehensive description of what this skill does]

## Prerequisites
- [Requirement 1]
- [Requirement 2]

## Instructions

### Phase 1: Preparation

[Detailed preparation steps]

### Phase 2: Execution

[Main execution logic]

### Phase 3: Validation

[How to verify results]

## Output Format

[Detailed output template]

## Examples

See examples.md for detailed usage examples.

## Troubleshooting

### Common Issues

**Problem:** [Issue description]
**Solution:** [How to resolve]
```

### Complete Example: Skill Creator

See `skill-creator/SKILL.md` for a complete, production-ready skill example.

---

## Best Practices Summary

✅ **DO:**
- Start with a clear overview
- Number steps sequentially
- Provide concrete examples
- Specify output formats
- Handle edge cases
- Keep descriptions concise (10-200 chars)
- Use lowercase, hyphenated names
- Test thoroughly

❌ **DON'T:**
- Write ambiguous instructions
- Skip important steps
- Assume prior knowledge
- Make descriptions too long or too short
- Forget to test with real queries
- Mix skills and tools (they're separate concepts)
- Use underscores in names
- Ignore edge cases
