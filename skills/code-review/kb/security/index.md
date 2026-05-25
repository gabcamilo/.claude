---
title: "Security"
domain: security
last_validated: "2026-04-02"
---

# Security — Review Knowledge

This domain covers application security rules aligned with OWASP top 10 and MercadoLibre's security requirements. It is the primary knowledge source for the security review scope, and supplements architecture and code-quality reviews.

## What This Domain Covers

- Input validation (allow-list strategy)
- Secrets handling (Fury Secrets Service)
- Logging safety (no PII, no secrets)
- Parameterized queries (never raw SQL)
- Secure random generation
- HMAC validation for webhooks

## Learning Path

1. Start with `quick-reference.md` for a red-flag checklist
2. Read all concepts — security rules are non-negotiable
3. Check `patterns/` for correct implementation examples

## Key Principle

Security rules from `.agentic-rules/java/java-security-patterns-rules_v1.md` take precedence over general guidance. Every code change must be evaluated against these rules. Security issues are always blocking severity.

## Live Docs

For vulnerability-specific guidance and dependency analysis, the review pipeline can use `ApplicationSecurityMCP` tools. This KB covers stable security patterns and rules.
