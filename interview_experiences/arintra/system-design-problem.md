Real-Time Event Processing System Design a system that ingests events from multiple sources (APIs, webhooks, streams), processes them in real-time with complex business rules, enriches data using external services, and triggers downstream actions. Requirements:
Handle 100K+ events per second with sub-second latency 
Guarantee at-least-once delivery with idempotency
Support replay and reprocessing of historical events
Dynamic rule configuration without downtime

