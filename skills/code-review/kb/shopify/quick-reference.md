---
title: "Shopify Quick Reference"
domain: shopify
last_validated: "2026-04-02"
---

# Shopify Integration — Quick Reference

## Decision Matrix

| Situation | Check | Severity |
|-----------|-------|----------|
| Webhook endpoint without HMAC validation | Must validate `X-Shopify-Hmac-SHA256` header | Blocking |
| Sequential API calls in loop for bulk data | Use Shopify Bulk Operations (GraphQL `bulkOperationRunQuery`) | Blocking |
| No rate limit handling on API calls | Must implement backoff/retry on 429 responses | Warning |
| GraphQL query fetching unused fields | Select only needed fields to reduce cost points | Warning |
| Hardcoded API version in URL | Use configurable version, track deprecation schedule | Suggestion |

## API Interaction Rules

| Pattern | Correct | Incorrect |
|---------|---------|-----------|
| Large data retrieval | Bulk Operations API or cursor-based pagination | Fetching all pages sequentially without throttle |
| Webhook security | HMAC-SHA256 validation before processing | Trusting payload without verification |
| Rate limiting | Exponential backoff on `429 Too Many Requests` | Retry immediately or ignore |
| GraphQL pagination | Cursor-based with `pageInfo { hasNextPage, endCursor }` | Offset-based pagination |
| Error handling | Check `userErrors` array in GraphQL responses | Only checking HTTP status code |

## Rate Limit Awareness

| API Type | Limit Model | Key Metric |
|----------|------------|------------|
| GraphQL Admin | Cost-based (1000 points/sec, 2000 max bucket) | `throttleStatus` in response extensions |
| REST Admin | 40 requests/sec per app | `X-Shopify-Shop-Api-Call-Limit` header |
| Bulk Operations | 1 concurrent operation per app per shop | Poll `currentBulkOperation` for status |

## Red Flags

- Webhook handler with no HMAC check
- API calls inside a loop without pagination or bulk operations
- No retry/backoff logic for external Shopify calls
- `userErrors` not checked in GraphQL mutation responses
