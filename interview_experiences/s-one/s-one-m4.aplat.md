# Candidate-Facing Take-Home Assignment

Thank you for your interest in becoming an engineering leader inside SentinelOne. As part of the interview process, we would like you to complete a take-home assignment that showcases your approach to project planning and execution. This project will stand as the background/context for the entire simulation.

---

# Context

As the Senior Engineering Manager for the Agent Platform (APLAT) team, you are tasked with leading the end-to-end delivery of a critical new feature: **Singularity Health Center**.

Currently, customers face challenges managing the operational health of their SentinelOne agents across millions of deployed endpoints. The Health Center will automatically ingest billions of daily telemetry events to detect high-impact operational anomalies – such as agents being disabled, anti-tampering being turned off, connectivity losses, or low disk space – and trigger actionable alerts.

---

# Current Ecosystem & Tech Stack

To ground your design, assume your team operates within SentinelOne’s current infrastructure:

- **Backend:** Microservices primarily written in Java, Go, and Python.
- **Frontend:** Modern web frameworks (e.g., React) for the SentinelOne console.
- **Infrastructure:** Kubernetes deployments via Helm on AWS/GCP, managed via Terraform.
- **CI/CD & Observability:** GitHub Actions, ArgoCD, and standard modern observability stacks.
- **Scale:** Your services must interact with millions of agents and process billions of daily requests.

---

# Your Challenge

You are inheriting a full-stack team of 10 engineers (Backend, Frontend, and QA) to deliver this project.

Your team owns the feature end-to-end: you will consume telemetry from a central Ingestion Gateway, process it, and build the UI screens in the SentinelOne console.

Please provide a comprehensive plan covering the following three areas:

---

# Task 1: Architectural Strategy & Operations

Design the high-level architecture required to support the Health Center.

## Scale & Performance

The system must:

- Process billions of daily requests.
- Detect anomalies within 5 minutes of occurrence.
- Serve data to the UI dashboard with an API latency of less than 200ms.

## Architecture

Detail your choices for:

- Data ingestion
- Event processing
- Storage

Highlight any components that could be developed into reusable platform services.

## Operations

How will you ensure the observability and reliability of this specific platform?

Walk us through how you would handle a hypothetical Sev-1 incident where the Health Center silently stops processing incoming agent events.

---

# Task 2: Execution, Delivery & Operational Distractions

Create a multi-quarter execution roadmap for this initiative, factoring in the realities of running a live platform.

## Phasing

How do you break this down into an MVP versus General Availability (GA) release?

Feel free to make and state your own assumptions about what features constitute the MVP.

## Dependency Risk

You discover that a critical external dependency — the core Ingestion Gateway team — is delayed by two months and won't be able to route the new health telemetry to your service on time.

How do you adapt your execution plan?

## Operational Drain

Over the last 3 weeks, there has been a 40% spike in customer support escalations because agents are incorrectly showing as "Offline" in the console.

This status logic relies on a legacy heartbeat microservice your team currently maintains, which the new Health Center will eventually replace.

How do you balance investigating and patching this legacy service (draining your resources) while keeping the Health Center MVP on track?

---

# Task 3: People & Talent Management

## Technical Conflict Resolution

A core requirement of the Health Center is **Alert Coalescing**.

Example:

Grouping 50 "anti-tampering disabled" events from the same agent over 10 minutes into a single alert to prevent spam.

### Engineer A

Wants to implement a dedicated stream-processing layer (e.g., Kafka Streams/Flink) for real-time aggregation before writing to the database.

### Engineer B

Argues this adds unnecessary infrastructure complexity and insists on writing raw events to the database, using asynchronous background cron jobs to coalesce them later.

Both have valid points regarding system complexity versus latency.

Walk us through how you would mediate this conflict and guide the team to a committed decision.

## Morale

How do you keep the team engaged and growing despite the operational distractions and dependency delays mentioned in Task 2?

---

# Rules of Engagement

## Timebox

We anticipate a high-quality submission will take realistically between 8 to 16 hours (1–2 days of effort).

We are looking for how you think, prioritize, and communicate.

This assignment will serve as the foundation for your interview loop.

## Audience

Design your slide deck as if you are presenting to a panel of:

- Peer Engineering Managers
- Architects
- VP of Engineering

## Tools

You are welcome to use AI tools to assist in generating or refining your deliverables.

However, be prepared to deeply defend every architectural and management decision during the live interview.

---

# Deliverables & Format

Please submit your assignment in a `.zip` file containing:

## 1. Slide Deck (PDF)

A 6–10 slide executive presentation summarizing:

- Architecture
- Execution Roadmap
- Major Risks and Mitigations

You will present this in your interview.

## 2. Written Document (PDF)

A 2–4 page narrative addressing:

- Technical trade-offs
- Handling operational drain
- Detailed people-management approach

## 3. Spreadsheet (Optional)

You may optionally include a spreadsheet for:

- Capacity planning
- Roadmap timelines
