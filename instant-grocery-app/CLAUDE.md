# System Design & Architecture Standards

##  🛠 Core Technical Principles
Scalability: Prefer horizontal scaling. Stateless services are the default.

Communication: Favor asynchronous event-driven patterns (Pub/Sub) over synchronous REST for inter-service communication to ensure fault tolerance.

Data Integrity: Use RDBMS for transactional data (ACID compliance). Use NoSQL/Key-Value stores only for high-throughput caching or unstructured metadata.

Observability: Every new service must include structured logging, health check endpoints, and OpenTelemetry hooks.

## 📝 Documentation Workflow
ADR First: Before implementing a major structural change, create an Architecture Decision Record in ADR-XXX-feature-name.md.

Diagrams: Use Mermaid.js syntax within Markdown files for sequence and entity-relationship diagrams. Generate the XML for a draw.io diagram of this architecture so I can import it.

API Design: Follow RESTful conventions. New endpoints must be documented in api-spec.md (OpenAPI format)

## 🏗 Design Patterns to Follow
Service Layer: Keep business logic out of controllers; use a dedicated service layer.

Repository Pattern: Abstract data access to make switching databases or mocking for tests easier.

Circuit Breakers: Implement circuit breaker patterns for all external API calls to prevent cascading failures.

## ⌨️ Claude CLI Commands & Shortcuts
claude --plan: Use this for high-level design discussions before writing code.

Review: Use claude "Perform a dry-run architectural review of my current plan for edge cases."
