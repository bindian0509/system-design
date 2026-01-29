# DSAR SQL Query Generator - System Design Document

## Executive Summary

An LLM-powered service that converts natural language Data Subject Access Requests (DSARs) into parameterized SQL queries for human review. The system does not execute queries directly—it generates them for compliance officers and support agents to review and execute through existing secure channels.

## Problem Statement

Organizations handling DSAR requests face a bottleneck: translating natural language requests like "show me all my data" into precise SQL queries requires:
1. Deep knowledge of the data schema
2. SQL expertise
3. Understanding of data privacy regulations
4. Time-consuming manual work

Current approaches either:
- Require extensive manual effort per request
- Expose too much data via static data export tools
- Lack the flexibility to handle varied request types

## Solution

An agentic LLM system that:
1. **Understands** natural language data requests
2. **Maps** requests to the appropriate database tables/columns
3. **Generates** safe, parameterized SQL queries
4. **Validates** queries against security constraints
5. **Presents** queries for human review before execution

## Document Index

| Document | Description |
|----------|-------------|
| [01-requirements.md](./01-requirements.md) | Functional and non-functional requirements |
| [02-architecture.md](./02-architecture.md) | System architecture and component design |
| [03-flow-diagrams.md](./03-flow-diagrams.md) | Request flow and sequence diagrams |
| [04-technology-choices.md](./04-technology-choices.md) | Technology stack with rationale |
| [05-scale.md](./05-scale.md) | Scalability considerations |
| [06-security-compliance.md](./06-security-compliance.md) | Security controls and compliance |
| [07-why-not-databook.md](./07-why-not-databook.md) | Why traditional data catalog approaches fail |
| [08-agentic-loop.md](./08-agentic-loop.md) | Research → Generate → Verify → Refine loop |
| [09-error-handling.md](./09-error-handling.md) | Error handling strategies |
| [10-query-equivalence.md](./10-query-equivalence.md) | Query equivalence checking |
