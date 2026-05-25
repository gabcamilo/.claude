---
title: "Fury Infrastructure Quick Reference"
domain: fury-infrastructure
last_validated: "2026-04-02"
---

# Fury Infrastructure — Quick Reference

## Decision Matrix

| Situation | Check | Severity |
|-----------|-------|----------|
| Credentials/secrets in code or config files | Must use Fury Secrets Service | Blocking |
| Custom HTTP headers added | Must have explicit approval | Blocking |
| CORS configuration at app level | Fury handles CORS — remove it | Blocking |
| Security headers set in code | Centrally managed by Fury — remove | Blocking |
| New external API integration | Uses MeliRestClient, not raw HttpClient | Warning |
| Missing SCOPE-based config split | Should use `application-{scope}.yml` | Warning |
| BigQueue consumer without error handling | Dead letter / retry strategy needed | Warning |
| KVS operations without TTL | Consider data lifecycle | Suggestion |

## SCOPE Mechanism

| SCOPE value | Config file loaded | Environment |
|-------------|-------------------|-------------|
| `local` | `application-local.yml` | Local dev |
| `test` | `application-test.yml` | Test/CI |
| (from Fury) | `application-{suffix}.yml` | Production |

The suffix is extracted from the last `-` segment of the SCOPE value.

## Service SDK Selection

| Need | Fury Service | SDK Pattern |
|------|-------------|-------------|
| Key-value storage | KVS | `FuryKvsClient` |
| Message queue | BigQueue (MeliQ) | Consumer/Producer config beans |
| Object storage | Object Storage | `FuryOsClient` |
| Internal API calls | REST | `MeliRestClient` |
| Secrets | Fury Secrets | Environment injection |
| Metrics | Datadog + New Relic | OpenTelemetry auto-instrumentation |

## Red Flags

- `String password = "..."` or `String apiKey = "..."` anywhere in source
- `@CrossOrigin` annotation on any controller
- `RestTemplate` or raw `HttpClient` for internal MercadoLibre APIs
- Secrets passed via query parameters or logged in any form
