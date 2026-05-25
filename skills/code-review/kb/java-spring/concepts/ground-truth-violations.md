---
title: "Ground-Truth Violation Patterns"
domain: java-spring
confidence: 0.95
last_validated: "2026-04-06"
---

# Ground-Truth Violation Patterns

These patterns are known to occur in this codebase. Every review MUST explicitly check for each one in the changed files. For each pattern, the reviewer must state "checked — found [where]" or "checked — not present in reviewed changes."

A pattern being pre-existing does NOT make it acceptable — it makes it tech debt (TD-xxx). The only patterns that can be silently skipped are those marked `intentional-deviation` in `docs/TECH_DEBT.md`.

## Architecture
- [ ] Domain model annotated with `@Entity`/`@Table` (domain layer should be pure POJOs)
- [ ] Controller/consumer injecting concrete service class instead of `*Port` interface
- [ ] Application service not implementing an inbound port interface from `domain/port/in/`
- [ ] Domain class importing `org.springframework.*` or `jakarta.persistence.*`
- [ ] Business logic in adapter layer (controller/consumer doing more than delegation)

## Security
- [ ] Endpoint parameters used without `@Valid` or null/format checks
- [ ] User-controlled input in URL construction (SSRF risk)
- [ ] Sensitive data (`shopUrl`, `jobId`, tokens) in exception messages or log statements
- [ ] Missing authentication/authorization on new endpoints
- [ ] `java.util.Random` or `Math.random()` used for security-sensitive values
- [ ] Raw SQL string concatenation (injection risk)

## Performance
- [ ] SQL execution inside a loop (N+1 pattern)
- [ ] Unbounded recursion or retry without max attempts
- [ ] Hardcoded small page sizes for paginated APIs (Shopify supports 250)
- [ ] Missing `@EntityGraph` or `JOIN FETCH` on JPA associations used in same request
- [ ] `FetchType.EAGER` on collections
- [ ] Missing pagination on potentially large result sets

## Code Quality
- [ ] Generic `RuntimeException` instead of domain-specific exceptions
- [ ] Redundant `@Transactional` on repository adapter methods (service already manages TX)
- [ ] `@Setter` on all fields making entities fully mutable without invariant protection
- [ ] Empty placeholder classes with no functionality
