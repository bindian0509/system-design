# System Design for Engineering Managers

A curated collection of production-grade system design case studies with complete implementations, architecture diagrams, and detailed documentation. Perfect for engineering managers, senior engineers, and anyone preparing for system design interviews.

---

## 📚 Table of Contents

| Topic                                                                   | Complexity | Key Concepts                                           |
| ----------------------------------------------------------------------- | ---------- | ------------------------------------------------------ |
| [🏦 Financial Clearing House](#-financial-clearing-house)               | Advanced   | Distributed Transactions, Graph Algorithms, Settlement |
| [📊 Fintech Data Platform](#-fintech-data-platform)                     | Advanced   | CDC, Event Streaming, HTAP, Data Lake                  |
| [🛒 E-Commerce Merchandise Browsing](#-e-commerce-merchandise-browsing) | Advanced   | Real-time Analytics, Personalization, Batch Processing |

---

## 🏦 Financial Clearing House

**[→ View Full Documentation](./financial-clearing-house/README.md)**

A complete interbank clearing house system that demonstrates how financial institutions settle transactions efficiently at the end of each business day.

### What You'll Learn

- **Pairwise Balance Calculation** — Calculate net balances between each pair of banks using efficient data structures
- **Multilateral Netting Algorithm** — Minimize actual money movements using graph-based optimization (93%+ netting efficiency)
- **Settlement System Design** — Fault-tolerant architecture for handling billions of transactions with exactly-once guarantees

### Key Highlights

```
Input: 9 transactions totaling $5,757 gross volume
Output: 2 settlement transfers totaling $387
Efficiency: 93.3% reduction in money movements
```

### Technical Stack

- **Languages:** Python, Java
- **Algorithms:** Greedy heap-based matching, Graph optimization
- **Patterns:** Immutable records, Two-phase settlement with saga

### 📁 Key Files

| File                                                                                                    | Description                         |
| ------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| [`clearing-house-settlement-design.md`](./financial-clearing-house/clearing-house-settlement-design.md) | Complete architecture documentation |
| [`clearing-house-system-flow.md`](./financial-clearing-house/clearing-house-system-flow.md)             | System flow diagrams                |
| [`src/python/`](./financial-clearing-house/src/python/)                                                 | Python implementation with demo     |
| [`src/java/`](./financial-clearing-house/src/java/)                                                     | Java implementation                 |

---

## 📊 Fintech Data Platform

**[→ View Full Documentation](./fintech-data-platform/fintech-data-architecture.md)**

A modern end-to-end data architecture for fintech payment platforms, demonstrating how to build real-time analytics, batch processing, and business intelligence capabilities at scale.

### What You'll Learn

- **Change Data Capture (CDC)** — Stream database changes in real-time using Debezium and Maxwell
- **Event-Driven Architecture** — Decouple services with Apache Kafka as the central event bus
- **Multi-Speed Data Processing** — Real-time (100ms), near real-time (2s), and batch (15 min) pipelines
- **Federated Query Layer** — Query any data source with SQL using Trino

### Architecture Overview

```
OLTP Layer (PostgreSQL, MySQL)
    ↓ CDC (Debezium, Maxwell)
Event Streaming (Apache Kafka)
    ↓ Fan-out
├── TiDB (HTAP) → Real-time reports
├── Apache Pinot → Sub-second dashboards
└── Data Lake (Parquet) → ML & Compliance
    ↓
Trino (Federated SQL)
    ↓
BI Tools (Querybook, Redash, Tableau)
```

### Technical Stack

- **Databases:** PostgreSQL, MySQL, TiDB
- **Streaming:** Apache Kafka, Debezium, Maxwell
- **Analytics:** Apache Pinot, Trino, Parquet
- **BI Tools:** Querybook, Redash, Tableau

### 📁 Key Files

| File                                                                                   | Description                                  |
| -------------------------------------------------------------------------------------- | -------------------------------------------- |
| [`fintech-data-architecture.md`](./fintech-data-platform/fintech-data-architecture.md) | Complete architecture with component details |
| [`e2e-system-diagram.md`](./fintech-data-platform/e2e-system-diagram.md)               | Visual end-to-end system diagram             |

---

## 🛒 E-Commerce Merchandise Browsing

**[→ View Full Documentation](./merchandise-listing/ecommerce-browsing-system-design.md)**

A comprehensive system design for large-scale e-commerce product discovery, handling 1M+ daily active users with real-time trending detection and personalized recommendations.

### What You'll Learn

- **Popularity Scoring** — Batch computation with time-decay for product rankings
- **Hot/Trending Detection** — Real-time streaming analytics with Apache Flink
- **Personalization Engine** — Collaborative filtering, content-based, and contextual re-ranking
- **API Design** — RESTful APIs with pagination, filtering, and caching strategies

### Scale Targets

| Metric              | Target   |
| ------------------- | -------- |
| Daily Active Users  | 1M+      |
| Products in Catalog | 100K+    |
| API Latency (p99)   | < 100ms  |
| Availability        | 99.9%+   |
| Peak Throughput     | 50K+ RPS |

### System Components

```
┌─────────────────────────────────────────────────────┐
│                   API Gateway                        │
└─────────────────────┬───────────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    ▼                 ▼                 ▼
┌─────────┐    ┌───────────┐    ┌─────────────┐
│ Browse  │    │ Ranking   │    │Personalize  │
│ Service │    │ Service   │    │  Service    │
└────┬────┘    └─────┬─────┘    └──────┬──────┘
     │               │                 │
     ▼               ▼                 ▼
┌─────────────────────────────────────────────────────┐
│        Redis (Popularity & Hot Items Cache)         │
└─────────────────────────────────────────────────────┘
     │                                 │
     ▼                                 ▼
┌──────────────┐              ┌───────────────┐
│  PostgreSQL  │              │  Data Lake    │
│  (Products)  │              │  (Events)     │
└──────────────┘              └───────────────┘
```

### Technical Stack

- **API:** Go/Rust (100K+ RPS per node)
- **Database:** PostgreSQL + Citus (sharding)
- **Cache:** Redis Cluster
- **Batch:** Apache Spark + Airflow
- **Streaming:** Apache Kafka + Flink
- **ML:** pgvector, XGBoost, Collaborative Filtering

### 📁 Key Files

| File                                                                                               | Description                         |
| -------------------------------------------------------------------------------------------------- | ----------------------------------- |
| [`ecommerce-browsing-system-design.md`](./merchandise-listing/ecommerce-browsing-system-design.md) | Complete 2000+ line design document |
| [`diagrams/architecture-diagrams.md`](./merchandise-listing/diagrams/architecture-diagrams.md)     | Architecture visualizations         |

---

## 🎯 Who Is This For?

- **Engineering Managers** — Understand system design trade-offs to guide technical decisions
- **Senior Engineers** — Learn production-grade patterns for distributed systems
- **Interview Candidates** — Practice with real-world system design problems
- **Tech Leads** — Reference architectures for greenfield projects

---

## 🔑 Common Patterns Across Designs

| Pattern                    | Used In                           |
| -------------------------- | --------------------------------- |
| Event Sourcing / CDC       | Fintech Data Platform, E-Commerce |
| CQRS                       | E-Commerce, Fintech Data Platform |
| Saga Pattern               | Financial Clearing House          |
| Exactly-Once Semantics     | Financial Clearing House, Fintech |
| Batch + Real-time (Lambda) | E-Commerce, Fintech Data Platform |
| Federated Queries          | Fintech Data Platform             |
| Sharding / Partitioning    | All designs                       |

---

## 🚀 Getting Started

### Run the Financial Clearing House Demo

```bash
# Python
cd financial-clearing-house/src/python
python3 demo.py

# Java
cd financial-clearing-house
mkdir -p target
find src/java -name "*.java" | xargs javac -d target
java -cp target com.clearinghouse.SettlementApp
```

---

## 📖 How to Use This Repository

1. **Start with the README** in each folder for an overview
2. **Read the design documents** (`.md` files) for architecture decisions
3. **Explore the code** for implementation details
4. **Run the demos** to see the systems in action

---

## 📝 License

MIT — See [LICENSE](./LICENSE) for details.

---

<p align="center">
  <i>Built for engineering managers who want to stay close to the code.</i>
</p>
