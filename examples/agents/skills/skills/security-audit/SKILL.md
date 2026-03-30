---
name: security-audit
description: Perform a security-focused audit of code, checking for OWASP Top 10 vulnerabilities and common attack vectors.
trigger:
  when:
    - user asks to check code for security issues
    - user asks to audit code for vulnerabilities
    - user mentions security review or penetration testing
  not_when:
    - user only asks about code style or formatting
    - user asks about performance optimization without security concern
required-tools:
  - execute_shell_command
---

# Security Audit

You are performing a security-focused code audit.

## Step 1 — Load references

Must read the OWASP reference: [./OWASP_TOP10.md](./OWASP_TOP10.md)

Also review the general code checklist for cross-reference: [../code-review/CHECKLIST.md](../code-review/CHECKLIST.md)

## Step 2 — Threat modeling

Identify:
- **Trust boundaries**: where does user input enter the system?
- **Data flow**: how does untrusted data propagate through the code?
- **Attack surface**: which functions are exposed to external input?

## Step 3 — Vulnerability scan

Check each OWASP category against the code. For each finding:

```
[VULN-001] <Category>
Severity: Critical / High / Medium / Low
Location: <file:line>
Description: <what's vulnerable>
Exploit scenario: <how an attacker could abuse this>
Remediation: <specific fix with code example>
```

## Step 4 — Remediated code

Provide the complete fixed version of the code with all vulnerabilities patched.

## Step 5 — Security summary

- Total vulnerabilities found (by severity)
- Risk rating: Critical / High / Medium / Low
- Top 3 priorities for the developer
