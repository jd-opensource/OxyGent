---
name: code-review
description: Review code snippets for bugs, style issues, and improvement suggestions.
trigger:
  when:
    - user asks to review code
    - user pastes code and asks for feedback
  not_when:
    - user asks to write new code from scratch
    - user asks to explain code without reviewing
required-tools:
  - execute_shell_command
---

# Code Review

You are performing a code review for $ARGUMENTS.

Follow the checklist below to ensure a thorough review.
Must see the full checklist at [./CHECKLIST.md](./CHECKLIST.md).

## Review Process

1. Read the code carefully
2. Check each item in the checklist
3. Provide specific, actionable feedback with line references
4. Suggest improved code where applicable

## Output Format

For each issue found:
- **Severity**: Critical / Warning / Suggestion
- **Location**: file and line
- **Issue**: description
- **Fix**: suggested change
