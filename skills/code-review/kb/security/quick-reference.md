---
title: "Security Quick Reference"
domain: security
last_validated: "2026-04-02"
---

# Security — Quick Reference

## Mandatory Rules (All Blocking)

| Rule | Check | Violation Example |
|------|-------|-------------------|
| No hardcoded secrets | Grep for literals assigned to vars named key/secret/password/token | `String apiKey = "sk-..."` |
| Parameterized queries | All DB queries use JPA/ORM or PreparedStatement | `"SELECT * FROM x WHERE id=" + userId` |
| Input validation | All controller params validated, allow-list preferred | Unvalidated `@RequestParam` passed to query |
| No PII in logs | Log statements don't include email, name, tokens, IDs | `log.info("User: " + user.getEmail())` |
| SecureRandom for tokens | Security-sensitive random uses `SecureRandom` | `new Random().nextInt()` for token generation |
| No eval/reflection | No `ScriptEngine`, `Class.forName` with user input | `Class.forName(request.getClassName())` |
| No CORS at app level | No `@CrossOrigin` or `CorsFilter` beans | `@CrossOrigin(origins = "*")` |
| No custom security headers | No `Content-Security-Policy`, `X-Frame-Options` in code | `response.setHeader("X-Frame-Options", ...)` |
| Server-side validation | Critical business logic validated server-side | Price/discount calculated client-side only |
| No GET for mutations | State changes use POST/PUT/DELETE | `@GetMapping("/delete/{id}")` |

## Sensitive Data Locations to Check

| Location | Allowed | Not Allowed |
|----------|---------|-------------|
| Log messages | Request IDs, operation types, error codes | Emails, names, tokens, passwords, PII |
| Query parameters | Pagination, filters, sort fields | Tokens, secrets, PII |
| Exception messages | Error codes, operation context | Stack traces with sensitive data, SQL |
| Error responses | Generic error messages with codes | Internal state, file paths, stack traces |

## Red Flags

- Any import of `java.util.Random` in non-test code
- String concatenation near SQL or shell commands
- `@RequestParam` or `@PathVariable` passed directly to external HTTP client URLs
- File upload handling without size/type validation
- Deserialization of untrusted input with `ObjectInputStream`
