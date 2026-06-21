# Long-Running Job Platform System Design Interview

This documentation captures a mature version of the interview simulation for an internal long-running job platform. It is written for Senior Engineering Manager / Director of Engineering calibration at Principal Engineer-level depth.

## Scenario

Build an internal platform for long-running business jobs such as:

- Quarterly business review reports generated from CRM data in custom formats.
- Daily customer health scores computed from multiple internal and external data sources.
- On-demand, scheduled, and recurring workflows.
- Custom ordered steps similar to workflow orchestration systems such as Airflow.

The platform serves 20 internal teams and supports roughly 440,000 job runs per day, averaging about 5 job starts per second with burst windows around 50 job starts per second.

## Documentation Map

- [Requirements Blueprint](requirements.md)
- [Reference Architecture](reference-architecture.md)
- [Data Model and Schemas](data-model.md)
- [Interview Questions and Mature Answers](interview-qa.md)
- [Calibration Report](calibration.md)

## Interviewer Guidance

Start with the problem statement only. Do not reveal scale, SLOs, workflow semantics, security requirements, or data retention expectations until the candidate asks. The goal is to evaluate whether the candidate can convert an ambiguous business prompt into a bounded, measurable, secure, and operable platform design.

Strong candidates should quickly discover that this is not just a queue-and-worker problem. It is a multi-tenant workflow control plane, durable orchestration system, zero-trust arbitrary-code execution platform, and business-critical reporting substrate.
