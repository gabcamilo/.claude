---
title: "MercadoLibre Fury"
domain: fury-infrastructure
last_validated: "2026-04-02"
---

# MercadoLibre Fury — Review Knowledge

This domain covers conventions for services running on Fury PaaS, MercadoLibre's deployment platform. It is a key knowledge source for architecture, security, and performance review scopes.

## What This Domain Covers

- Fury Secrets Service (never hardcode credentials)
- BigQueue (message queue) conventions
- KVS (key-value store) usage patterns
- SCOPE mechanism for environment-specific configuration
- Observability (OpenTelemetry, New Relic, Datadog)
- MeliRestClient for internal API communication

## Learning Path

1. Start with `quick-reference.md` for a decision matrix
2. Read `concepts/fury-secrets.md` — security-critical, affects all reviews
3. Check `concepts/fury-deployment.md` for SCOPE and configuration patterns
4. See `patterns/` for implementation examples

## Key Principle

Fury manages infrastructure concerns (secrets, routing, scaling, headers). Applications should not duplicate what Fury provides — no application-level CORS, no hardcoded secrets, no custom security headers. Use the platform's SDKs and conventions.

## Live Docs

For volatile information (current SDK versions, API changes), the review pipeline uses **FuryDocsExplorer** agent with `meli-docs-fury` MCP tools. This KB covers stable conventions only.
