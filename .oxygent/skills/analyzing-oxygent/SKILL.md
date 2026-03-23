---
name: analyzing-oxygent
description: Explore and understand the OxyGent framework structure, components, and implementation patterns.
trigger:
  when:
    - user asks about OxyGent framework internals
    - user wants to explore the codebase structure
  not_when:
    - user asks about general programming unrelated to OxyGent
---

# OxyGent Framework Explorer

## Introduction

This skill assists in navigating and understanding the OxyGent codebase. Use it when you need to investigate framework internals, discover available components, or locate relevant code sections.

## Core Capabilities

The explorer offers these main functions:

- Browse the example implementations to learn practical usage patterns
- Examine source code to understand component behaviors
- Search for specific classes, functions, or patterns across the project

## Navigation Guide

### Locating Code Examples

The `examples/` directory contains demonstration files showcasing various framework features:

```bash
ls examples/agents/
```

Notable demonstration files include:
- Agent setup examples: `demo_single_agent.py`, `demo_react_agent.py`
- Skill integration examples: `demo_skill_agent.py`, `demo_skill_agent2.py`

For viewing any example:

```bash
cat examples/agents/demo_skill_agent.py
```

### Examining Source Structure

The core implementation resides in the `oxygent/` directory:

```bash
# Core agent implementations
ls oxygent/oxy/agents/

# Skill system components
ls oxygent/skills/

# Preset tool definitions
ls oxygent/oxy/preset_tools/
```

To inspect specific source files:

```bash
cat oxygent/oxy/agents/skill_agent.py
```

### Finding Specific Implementations

Use grep to locate definitions and patterns:

```bash
grep -r "class SkillAgent" oxygent/ --include="*.py"
grep -r "def query" oxygent/ --include="*.py"
```

## Recommended Workflow

When investigating OxyGent-related questions:

1. **Understanding usage** → Browse examples first
2. **Checking implementation** → Examine relevant source files
3. **Finding definitions** → Use grep with appropriate patterns

## Practical Commands Reference

| Purpose | Command |
|---------|---------|
| List agent examples | `ls examples/agents/` |
| View a source file | `cat oxygent/oxy/agents/<name>.py` |
| Search class definitions | `grep -r "class <Name>" oxygent/ --include="*.py"` |
| Explore directory tree | `tree -L 2 oxygent/oxy/` |
