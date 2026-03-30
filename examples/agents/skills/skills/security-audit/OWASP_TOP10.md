# OWASP Top 10 Quick Reference

## A01: Broken Access Control
- Missing authorization checks on sensitive endpoints
- IDOR (Insecure Direct Object References)
- Accessing other users' data by changing IDs

## A02: Cryptographic Failures
- Storing passwords in plaintext
- Using weak hashing (MD5, SHA1 without salt)
- Transmitting sensitive data without TLS

## A03: Injection
- SQL injection via string concatenation
- Command injection via os.system() / subprocess with shell=True
- LDAP, XPath, NoSQL injection

## A04: Insecure Design
- Missing rate limiting on authentication
- No account lockout after failed attempts
- Business logic flaws

## A05: Security Misconfiguration
- Default credentials left in place
- Verbose error messages exposing internals
- Unnecessary features enabled

## A06: Vulnerable Components
- Known CVEs in dependencies
- Outdated libraries with security patches available

## A07: Authentication Failures
- Weak password policies
- Missing multi-factor authentication
- Session tokens in URLs

## A08: Data Integrity Failures
- Insecure deserialization (pickle.loads on untrusted data)
- Missing integrity checks on updates
- Unsigned JWTs

## A09: Logging & Monitoring Failures
- Sensitive data in logs (passwords, tokens)
- No logging of authentication failures
- Missing alerting on suspicious activity

## A10: Server-Side Request Forgery (SSRF)
- User-controlled URLs in server-side HTTP requests
- Missing URL validation and allowlists
