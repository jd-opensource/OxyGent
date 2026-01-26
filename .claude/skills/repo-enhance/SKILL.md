---
name: repo-enhance
description: Deep repository analysis with competitive research to brainstorm enhancement ideas using codebase exploration, web search, and multi-agent exploration
version: "1.0.0"
author: "OxyGent Team"

allowed-tools:
  - Read
  - Glob
  - Grep
  - Task
  - Bash
  - WebSearch

model: claude-opus-4-5
---

# Repository Enhancement Brainstorming

## Overview

This skill performs comprehensive repository analysis by combining codebase exploration, documentation extraction, and competitive research on popular AI agent frameworks to generate actionable enhancement ideas.

## Triggers

This skill should be activated when:
- User requests repository improvement planning
- User asks for feature gap analysis
- User requests competitive analysis for AI agent frameworks
- User asks about architecture enhancement brainstorming
- User asks "How can we improve this repo" or similar questions

## Parameters

When activating this skill, identify these parameters from user request:
- **--focus**: Target analysis area (core|agents|tools|docs|all) - default: all
- **--compare**: Comma-separated list of frameworks to research - default: claude-agent,codex,langchain,langgraph,autogen,crewai
- **--depth**: Analysis depth (quick|standard|deep) - default: standard

## Instructions

### Phase 1: Repository Overview (15% effort)

**Objective**: Understand current codebase structure and capabilities

**Actions**:
1. Use Explore agent to analyze repository structure:
   - Identify core modules and their purposes
   - Map architecture patterns (agents, tools, LLMs, memory)
   - Document existing features and capabilities
   - Note code quality patterns and testing coverage

2. Create structured overview in your analysis:
   ```yaml
   current_state:
     architecture: [components]
     features: [capabilities]
     patterns: [design patterns used]
     gaps: [identified limitations]
   ```

### Phase 2: Documentation Extraction (20% effort)

**Objective**: Extract comprehensive documentation from the repository

**Actions**:
1. Use Read tool to examine key documentation files:
   - README.md for project overview
   - Any docs/ directory for detailed documentation
   - PRD files for product requirements
   - Code comments and docstrings

2. Extract key insights:
   - API surface and interfaces
   - Usage patterns and examples
   - Documentation gaps
   - Architecture decisions

### Phase 3: Competitive Research (30% effort)

**Objective**: Analyze popular AI agent frameworks for feature inspiration

**Research Targets** (parallel execution):
- **Claude Agent SDK**: Official Anthropic agent patterns
- **OpenAI Codex/Assistants**: OpenAI's agent architecture
- **LangChain**: Popular LLM orchestration framework
- **LangGraph**: Graph-based agent workflows
- **AutoGen**: Microsoft's multi-agent framework
- **CrewAI**: Role-based agent collaboration
- **Semantic Kernel**: Microsoft's AI orchestration

**Actions**:
1. Use WebSearch for each framework:
   - Search: "[framework] agent architecture 2024"
   - Search: "[framework] features capabilities"
   - Search: "[framework] vs alternatives comparison"

2. Extract from research:
   - Key features and capabilities
   - Architectural patterns
   - Unique differentiators
   - Best practices

### Phase 4: Gap Analysis (15% effort)

**Objective**: Identify feature gaps and enhancement opportunities

**Analysis Matrix**:
Create a comparison showing:
```yaml
feature_comparison:
  current_repo:
    has: [list of existing features]
    missing: [features others have]
    unique: [differentiating features]

  competitors:
    langchain: [key features]
    langgraph: [key features]
    autogen: [key features]
    crewai: [key features]
```

### Phase 5: Enhancement Brainstorming (20% effort)

**Objective**: Generate prioritized enhancement ideas

**Categories**:

1. **Core Architecture Enhancements**
   - Agent orchestration patterns
   - Memory and state management
   - Tool integration improvements

2. **New Feature Ideas**
   - Graph-based workflows (inspired by LangGraph)
   - Role-based agents (inspired by CrewAI)
   - Streaming and real-time capabilities
   - Multi-modal support

3. **Developer Experience**
   - API simplification
   - Documentation improvements
   - Example and template additions
   - CLI enhancements

4. **Performance & Reliability**
   - Caching strategies
   - Error handling patterns
   - Observability and tracing
   - Testing infrastructure

## Output Format

Generate a comprehensive report with this structure:

```markdown
# Repository Enhancement Analysis

## Executive Summary
[Key findings and top 5 recommendations]

## Current State Analysis
### Architecture Overview
### Feature Inventory
### Identified Strengths
### Current Limitations

## Competitive Landscape
### Framework Comparison Matrix
### Feature Gap Analysis
### Industry Trends

## Enhancement Recommendations

### Priority 1: Critical Improvements
[High-impact, feasible enhancements]

### Priority 2: Feature Additions
[New capabilities to consider]

### Priority 3: Long-term Vision
[Strategic architectural improvements]

## Implementation Roadmap
[Suggested sequencing and dependencies]

## Sources and References
[All researched sources with links]
```

## Depth Levels

Adjust your analysis based on the depth parameter:

- **Quick**: Fast overview with top 3 enhancement ideas (~5 minutes, minimal research)
- **Standard**: Full analysis with competitive research (~15 minutes, comprehensive report)
- **Deep**: Extensive research with detailed comparison matrix (~30 minutes)

## Examples

### Example 1: Quick Analysis
```
User: /repo-enhance --depth quick
→ Fast overview with top 3 enhancement ideas
→ ~5 minutes, minimal research
```

### Example 2: Standard Analysis
```
User: /repo-enhance
→ Full analysis with competitive research
→ ~15 minutes, comprehensive report
```

### Example 3: Deep Competitive Analysis
```
User: /repo-enhance --compare langchain,langgraph,autogen,crewai --depth deep
→ Extensive research on specific frameworks
→ ~30 minutes, detailed comparison matrix
```

### Example 4: Focused Analysis
```
User: /repo-enhance --focus agents --compare autogen,crewai
→ Target agent orchestration patterns
→ Compare with multi-agent frameworks only
```

## Boundaries

**This Skill WILL:**
- Analyze current repository structure and capabilities
- Research popular AI agent frameworks for inspiration
- Generate actionable enhancement recommendations
- Provide prioritized implementation suggestions
- Create comprehensive documentation of findings

**This Skill WILL NOT:**
- Make changes to the codebase directly
- Implement enhancements without user approval
- Access private/proprietary framework documentation
- Make subjective quality judgments without evidence
- Recommend changes that break existing functionality
