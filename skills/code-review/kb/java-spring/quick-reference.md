---
title: "Java / Spring Boot Quick Reference"
domain: java-spring
last_validated: "2026-04-02"
---

# Java / Spring Boot — Quick Reference

## Architecture Decision Matrix

| Situation | Check | Severity |
|-----------|-------|----------|
| New class in `domain/` | No Spring/framework imports | Blocking |
| New class in `infrastructure/` | Implements a port interface from `domain/port/out/` | Blocking |
| Service calling external API | Goes through a port, not direct HTTP call | Blocking |
| Controller with business logic | Logic belongs in application service | Blocking |
| Application service with SQL/HTTP | Must delegate to outbound port | Blocking |
| Field injection (`@Autowired` on field) | Use constructor injection | Warning |
| `@Transactional` on repository method | Should be at service layer | Warning |
| Derived query name > 3 predicates | Use `@Query` instead | Suggestion |

## Layer Placement

| Class Type | Correct Package | Wrong Package |
|------------|----------------|---------------|
| Business model/entity | `domain/model/` | `infrastructure/` |
| Business exception | `domain/exception/` | `application/` |
| Use case interface | `domain/port/in/` | `application/` |
| Repository interface | `domain/port/out/` | `infrastructure/` |
| Use case implementation | `application/service/` | `domain/` |
| REST controller | `infrastructure/adapter/in/rest/` | `application/` |
| JPA repository impl | `infrastructure/adapter/out/persistence/` | `domain/` |
| External API client | `infrastructure/adapter/out/integration/` | `application/` |
| Spring config | `infrastructure/config/` | anywhere else |

## Injection Pattern

| Pattern | Status |
|---------|--------|
| Constructor injection (implicit `@Autowired`) | Preferred |
| `@Autowired` on constructor | Acceptable |
| `@Autowired` on field | Avoid — harder to test |
| Setter injection | Avoid unless optional dependency |

## JPA Red Flags

- Repository call inside a loop → N+1 query
- `FetchType.EAGER` on collection → performance bomb
- `equals()`/`hashCode()` using DB-generated ID → broken Set behavior
- `@Transactional` spanning external HTTP calls → long-held DB connections
- Missing `@EntityGraph` or `JOIN FETCH` on associations used in the same request
