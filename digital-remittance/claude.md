# CLAUDE.md — Digital Remittance Platform System Design

## Project

Interview-ready system design documentation for a Wise/Remitly-scale cross-border remittance platform.

## Structure

- `README.md` — Master overview with architecture diagram, tech stack, and links to all design docs.
- `design/` — Modular topic documents (17 docs covering architecture through end-to-end walkthrough).

## Conventions

- All diagrams use **Mermaid** syntax (rendered natively in GitHub/GitLab).
- Each design doc follows a consistent structure: **Overview**, **Details**, **Diagrams**, **Design Rationale**.
- Use tables for comparisons and trade-off analysis.
- Keep documents focused on *why* decisions were made, not just *what* was chosen.

## Key Design Decisions

- **Service-per-domain microservices** — Each bounded context (KYC, compliance, ledger, etc.) owns its data and API surface.
- **Saga orchestration** — Long-running transfers use an orchestrator-based saga to coordinate across services with compensating transactions on failure.
- **Event-sourced audit trails** — All state transitions are published to Kafka and stored as an immutable event log for compliance and debugging.
- **Double-entry ledger** — Every money movement records balanced debit/credit entries; no funds appear or disappear without a matching contra-entry.
