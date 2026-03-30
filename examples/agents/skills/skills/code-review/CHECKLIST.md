# Code Review Checklist

## 1. Correctness
- [ ] Off-by-one errors in loops and slices
- [ ] Null / None / undefined reference risks
- [ ] Unhandled edge cases (empty input, zero, negative values)
- [ ] Incorrect return types or missing returns
- [ ] Race conditions in concurrent code

## 2. Security
- [ ] SQL injection (string concatenation in queries)
- [ ] XSS in user-facing output
- [ ] Command injection via unsanitized shell calls
- [ ] Hardcoded secrets, API keys, or credentials
- [ ] Insecure deserialization (pickle, eval, exec)
- [ ] Path traversal in file operations

## 3. Error Handling
- [ ] Bare except clauses catching too broadly
- [ ] Swallowed exceptions (catch and ignore)
- [ ] Missing cleanup in error paths (files, connections)
- [ ] Unclear or missing error messages

## 4. Performance
- [ ] O(n^2) or worse algorithms where O(n) is possible
- [ ] Repeated computation that could be cached
- [ ] Unnecessary memory allocation in hot paths
- [ ] Missing database indexes implied by queries

## 5. Maintainability
- [ ] Dead code or unused imports
- [ ] Functions longer than 30 lines
- [ ] Magic numbers without named constants
- [ ] Inconsistent naming conventions
