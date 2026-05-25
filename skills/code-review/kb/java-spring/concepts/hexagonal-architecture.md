---
title: "Hexagonal Architecture"
domain: java-spring
confidence: 0.95
last_validated: "2026-04-02"
related:
  - title: "Port-Adapter Pattern"
    path: "../patterns/port-adapter-pattern.md"
  - title: "Service Orchestration"
    path: "../patterns/service-orchestration.md"
---

# Hexagonal Architecture

## Overview

Hexagonal architecture (ports & adapters) isolates business logic from infrastructure concerns. The domain layer is the core — it defines what the system does. Infrastructure adapts the outside world to the domain's interfaces. This separation makes business logic testable without frameworks and protects it from infrastructure changes.

## The Rule

Three layers with strict dependency direction:

```
infrastructure/ → application/service/ → domain/
     (outer)          (middle)            (inner)
```

- **domain/**: Pure business logic. Models, exceptions, policies, port interfaces. Zero framework imports.
- **application/service/**: Use case implementations. Orchestrates domain logic through ports. May import Spring's `@Service` and `@Transactional`.
- **infrastructure/**: Framework adapters — REST controllers (in), JPA repositories (out), API clients (out), Spring config.

```java
// Correct — domain port defines the contract
// domain/port/out/ProductRepository.java
public interface ProductRepository {
    Optional<Product> findById(ProductId id);
    void save(Product product);
}

// infrastructure/adapter/out/persistence/JpaProductRepository.java
@Repository
public class JpaProductRepository implements ProductRepository {
    // JPA implementation details here
}

// Wrong — domain depending on infrastructure
// domain/service/ProductValidator.java
import org.springframework.data.jpa.repository.JpaRepository; // VIOLATION
```

## Quick Reference

| Aspect | Expected | Violation |
|--------|----------|-----------|
| Domain imports | Only `java.*`, other domain classes | Spring, JPA, HTTP framework imports |
| Dependency direction | Outer → inner only | Domain importing infrastructure |
| Port definition | Interface in `domain/port/` | Concrete class in domain |
| Adapter location | `infrastructure/adapter/in/` or `out/` | Adapter in `application/` or `domain/` |
| Business rules | In domain models or domain services | In controllers or application services |

## Common Mistakes

1. **Leaking JPA into domain** — Using `@Entity` on domain models directly. Domain models should be pure; map to/from JPA entities in the persistence adapter.
2. **Bypassing ports** — Application service directly instantiating an HTTP client instead of calling an outbound port.
3. **Business logic in controllers** — Validation, transformation, or decision logic in REST controllers instead of delegating to use cases.
4. **Fat application services** — Services that contain business rules instead of just orchestrating domain calls.

## Related

- [Port-Adapter Pattern](../patterns/port-adapter-pattern.md) — Concrete implementation examples
- [Service Orchestration](../patterns/service-orchestration.md) — How application services coordinate domain logic
