# Singularity Health Center Interview Packet

This workspace contains an implementation-level architecture package for the SentinelOne Agent Platform interview prompt.

## Files

- [01-architecture-plan.md](01-architecture-plan.md) - End-to-end system architecture, component responsibilities, APIs, data model, scaling model, resiliency, security, and implementation choices.
- [02-delivery-and-operations-plan.md](02-delivery-and-operations-plan.md) - Senior engineering manager delivery plan, team topology, milestones, rollout, observability, incident posture, and risk management.
- [03-diagrams.md](03-diagrams.md) - Mermaid diagrams for architecture, streaming flow, alert lifecycle, data model, deployment topology, and rollout.
- [04-edge-cases-and-trick-questions.md](04-edge-cases-and-trick-questions.md) - Interview edge cases, follow-up traps, and concise answers.
- [05-interview-talk-track.md](05-interview-talk-track.md) - A structured L7+ interview narrative with tradeoffs and decision framing.
- [06-challenge-1-architecture-operations.md](06-challenge-1-architecture-operations.md) - Consolidated response for Challenge 1: architecture strategy, scale, reusable platform services, observability, reliability, and Sev-1 incident handling.
- [07-challenge-2-execution-delivery-distractions.md](07-challenge-2-execution-delivery-distractions.md) - Consolidated response for Challenge 2: multi-quarter roadmap, MVP vs GA scope, dependency delay response, and balancing legacy operational escalations.
- [08-challenge-3-people-talent-management.md](08-challenge-3-people-talent-management.md) - Consolidated response for Challenge 3: technical conflict resolution, alert coalescing decision process, morale, growth, and team engagement.
- [09-overall-project-management-gantt.md](09-overall-project-management-gantt.md) - Overall project management timeline, Gantt chart, resource allocation, critical path, and operating cadence.

## Problem Summary

Singularity Health Center detects high-impact operational anomalies across millions of SentinelOne agents by ingesting billions of daily telemetry events, maintaining near-real-time endpoint health state, and producing actionable, deduplicated alerts in the SentinelOne console and downstream integrations.

The design assumes:

- Backend microservices in Java, Go, and Python.
- React-based SentinelOne console.
- Kubernetes on AWS/GCP, deployed with Helm and Terraform.
- GitHub Actions, ArgoCD, and modern observability.
- Multi-tenant SaaS scale with millions of agents and billions of daily telemetry events.

## Recommended Interview Position

Lead with this:

> I would separate raw telemetry ingestion from health-state derivation and alert delivery. The system should be streaming-first, tenant-aware, idempotent, and resilient to late, duplicated, and missing events. The product value is not just detecting anomalies; it is producing trustworthy, deduplicated, explainable, and actionable health findings at customer scale.

For the updated interview prompt, emphasize that the team consumes from an existing central Ingestion Gateway. The team-owned system starts at the durable telemetry stream and owns processing, health state, alerting, APIs, and UI.

For delivery/execution questions, emphasize phased value delivery, explicit dependency management, and protecting a live platform while reducing future operational load.

For people-management questions, emphasize principled decision-making, psychological safety, clear ownership, and preserving team energy through visible progress and growth opportunities.
