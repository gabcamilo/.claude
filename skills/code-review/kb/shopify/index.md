---
title: "Shopify Integration"
domain: shopify
last_validated: "2026-04-02"
---

# Shopify Integration — Review Knowledge

This domain covers patterns for integrating with Shopify APIs, primarily the GraphQL Admin API and webhook system. It supplements performance and architecture reviews.

## What This Domain Covers

- Shopify GraphQL API conventions and query patterns
- Webhook lifecycle and HMAC validation
- Rate limiting awareness and throttling strategies
- Bulk operations for large data sets
- Fulfillment flow (order lifecycle)

## Learning Path

1. Start with `quick-reference.md` for API interaction rules
2. Read `concepts/webhook-handling.md` for security-critical webhook validation
3. Check `concepts/rate-limiting.md` for performance-critical patterns
4. See `patterns/` for implementation examples

## Key Principle

Shopify APIs have strict rate limits and throttling. Every integration must be designed with rate limiting in mind — use bulk operations for large datasets, implement backoff strategies, and never make unbounded sequential API calls.

## Live Docs

For current API versions, schema changes, and deprecation notices, the review pipeline uses **DocsExplorer** with Shopify MCP tools (`mcp__shopify-dev__*`). This KB covers stable integration patterns only.
