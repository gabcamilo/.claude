---
title: "Java / Spring Boot"
domain: java-spring
last_validated: "2026-04-02"
---

# Java / Spring Boot — Review Knowledge

This domain covers conventions and rules for Java 21 + Spring Boot services following hexagonal architecture. It is the primary knowledge source for architecture and code-quality review scopes.

## What This Domain Covers

- Hexagonal architecture layer rules and dependency direction
- Spring Boot annotation conventions and injection patterns
- JPA/Hibernate best practices (entities, transactions, fetching)
- Testing conventions (JUnit 5, TestContainers, naming)

## Learning Path

1. Start with `quick-reference.md` for a decision matrix during reviews
2. Read `concepts/hexagonal-architecture.md` for layer boundary rules
3. Check `concepts/spring-boot-conventions.md` for annotation patterns
4. Review `concepts/jpa-patterns.md` for persistence rules
5. See `patterns/` for concrete implementation examples

## Key Principle

Domain code must have zero framework dependencies. Dependencies point inward: infrastructure → application → domain, never the reverse. Every external integration goes through a port (interface in domain) with an adapter (implementation in infrastructure).
