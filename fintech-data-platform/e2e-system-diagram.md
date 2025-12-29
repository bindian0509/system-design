# Fintech Payment Platform - End-to-End System Design

```
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                                                              ║
║                              FINTECH PAYMENT PLATFORM - END-TO-END DATA ARCHITECTURE                                        ║
║                                                                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                              ║
║    ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   ║
║    │                                           MICROSERVICES LAYER (OLTP)                                                │   ║
║    │                                                                                                                     │   ║
║    │      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐                │   ║
║    │      │ 💳 Payment Svc  │      │ 💰 Wallet Svc   │      │ 👤 User Svc     │      │ 🏪 Merchant Svc │                │   ║
║    │      │   (Java/Spring) │      │   (Go/gRPC)     │      │   (Node.js)     │      │   (Python)      │                │   ║
║    │      └────────┬────────┘      └────────┬────────┘      └────────┬────────┘      └────────┬────────┘                │   ║
║    │               │                        │                        │                        │                         │   ║
║    │               ▼                        ▼                        ▼                        ▼                         │   ║
║    │      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐                │   ║
║    │      │   PostgreSQL    │      │   PostgreSQL    │      │     MySQL       │      │     MySQL       │                │   ║
║    │      │  ┌───────────┐  │      │  ┌───────────┐  │      │  ┌───────────┐  │      │  ┌───────────┐  │                │   ║
║    │      │  │ payments  │  │      │  │ wallets   │  │      │  │ users     │  │      │  │ merchants │  │                │   ║
║    │      │  │ refunds   │  │      │  │ balances  │  │      │  │ kyc_data  │  │      │  │ terminals │  │                │   ║
║    │      │  │ disputes  │  │      │  │ txn_logs  │  │      │  │ sessions  │  │      │  │ mdr_rates │  │                │   ║
║    │      │  └───────────┘  │      │  └───────────┘  │      │  └───────────┘  │      │  └───────────┘  │                │   ║
║    │      └────────┬────────┘      └────────┬────────┘      └────────┬────────┘      └────────┬────────┘                │   ║
║    │               │                        │                        │                        │                         │   ║
║    └───────────────┼────────────────────────┼────────────────────────┼────────────────────────┼─────────────────────────┘   ║
║                    │                        │                        │                        │                             ║
║                    │        WAL             │        WAL             │      BINLOG            │      BINLOG                 ║
║                    ▼                        ▼                        ▼                        ▼                             ║
║    ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   ║
║    │                                      CHANGE DATA CAPTURE (CDC) LAYER                                                │   ║
║    │                                                                                                                     │   ║
║    │      ┌───────────────────────────────────────────┐      ┌───────────────────────────────────────────┐              │   ║
║    │      │              🔄 DEBEZIUM                  │      │              ⚡ MAXWELL                    │              │   ║
║    │      │         (PostgreSQL CDC)                  │      │           (MySQL CDC)                     │              │   ║
║    │      │                                           │      │                                           │              │   ║
║    │      │  • Reads PostgreSQL WAL                   │      │  • Reads MySQL binlog                     │              │   ║
║    │      │  • Exactly-once delivery                  │      │  • Low latency (~50ms)                    │              │   ║
║    │      │  • Schema evolution support               │      │  • Lightweight daemon                     │              │   ║
║    │      │  • Kafka Connect integration              │      │  • JSON event format                      │              │   ║
║    │      │                                           │      │                                           │              │   ║
║    │      └─────────────────────┬─────────────────────┘      └─────────────────────┬─────────────────────┘              │   ║
║    │                            │                                                  │                                    │   ║
║    │                            └──────────────────────┬───────────────────────────┘                                    │   ║
║    │                                                   │                                                                │   ║
║    │                                                   ▼                                                                │   ║
║    │                         ╔═══════════════════════════════════════════════════╗                                      │   ║
║    │                         ║              📨 APACHE KAFKA                      ║                                      │   ║
║    │                         ║           (Event Streaming Platform)              ║                                      │   ║
║    │                         ║                                                   ║                                      │   ║
║    │                         ║   Topics:                                         ║                                      │   ║
║    │                         ║   ├── cdc.payments.transactions                   ║                                      │   ║
║    │                         ║   ├── cdc.payments.refunds                        ║                                      │   ║
║    │                         ║   ├── cdc.wallets.balances                        ║                                      │   ║
║    │                         ║   ├── cdc.users.profiles                          ║                                      │   ║
║    │                         ║   └── cdc.merchants.settlements                   ║                                      │   ║
║    │                         ║                                                   ║                                      │   ║
║    │                         ╚═══════════════════════════════════════════════════╝                                      │   ║
║    │                                                   │                                                                │   ║
║    └───────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────┘   ║
║                                                        │                                                                    ║
║                        ┌───────────────────────────────┼───────────────────────────────┐                                    ║
║                        │                               │                               │                                    ║
║                        ▼                               ▼                               ▼                                    ║
║    ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   ║
║    │                                         DATA PROCESSING & STORAGE LAYER                                             │   ║
║    │                                                                                                                     │   ║
║    │   ┌─────────────────────────────┐   ┌─────────────────────────────┐   ┌─────────────────────────────────────────┐  │   ║
║    │   │       🗄️ TiDB               │   │      📊 APACHE PINOT        │   │           🏔️ DATA LAKE                  │  │   ║
║    │   │    (HTAP Database)          │   │    (Real-time OLAP)         │   │        (Cloud Object Storage)          │  │   ║
║    │   │                             │   │                             │   │                                         │  │   ║
║    │   │  ┌───────────────────────┐  │   │  ┌───────────────────────┐  │   │   ┌─────────────────────────────────┐   │  │   ║
║    │   │  │ • MySQL compatible    │  │   │  │ • Sub-second queries  │  │   │   │      📦 APACHE PARQUET          │   │  │   ║
║    │   │  │ • Horizontal scaling  │  │   │  │ • Real-time ingestion │  │   │   │                                 │   │  │   ║
║    │   │  │ • HTAP workloads      │  │   │  │ • User-facing dashb.  │  │   │   │  s3://fintech-datalake/         │   │  │   ║
║    │   │  │ • Strong consistency  │  │   │  │ • Star-tree indexing  │  │   │   │  ├── payments/                  │   │  │   ║
║    │   │  └───────────────────────┘  │   │  └───────────────────────┘  │   │   │  │   └── year=2025/month=12/    │   │  │   ║
║    │   │                             │   │                             │   │   │  ├── users/                     │   │  │   ║
║    │   │  Tables:                    │   │  Tables:                    │   │   │  ├── merchants/                 │   │  │   ║
║    │   │  • unified_transactions     │   │  • realtime_payments        │   │   │  └── settlements/               │   │  │   ║
║    │   │  • aggregated_balances      │   │  • merchant_metrics         │   │   │                                 │   │  │   ║
║    │   │  • settlement_ledger        │   │  • fraud_signals            │   │   │  Format: Columnar, Compressed   │   │  │   ║
║    │   │                             │   │  • user_activity            │   │   │  Partitioned: date, entity_type │   │  │   ║
║    │   │                             │   │                             │   │   └─────────────────────────────────┘   │  │   ║
║    │   │  Latency: 500ms - 2s        │   │  Latency: 100ms - 500ms     │   │                                         │  │   ║
║    │   │  Use: Reports, sync reads   │   │  Use: Live dashboards       │   │   Latency: 5-15 min (batch)            │  │   ║
║    │   │                             │   │                             │   │   Use: ML, Compliance, Historical      │  │   ║
║    │   └─────────────────────────────┘   └─────────────────────────────┘   └─────────────────────────────────────────┘  │   ║
║    │                                                                                                                     │   ║
║    └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘   ║
║                        │                               │                               │                                    ║
║                        └───────────────────────────────┼───────────────────────────────┘                                    ║
║                                                        │                                                                    ║
║                                                        ▼                                                                    ║
║    ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   ║
║    │                                          FEDERATED QUERY LAYER                                                      │   ║
║    │                                                                                                                     │   ║
║    │                              ╔═══════════════════════════════════════════════════════════════╗                      │   ║
║    │                              ║                      🔍 TRINO                                 ║                      │   ║
║    │                              ║             (Distributed SQL Query Engine)                    ║                      │   ║
║    │                              ║                                                               ║                      │   ║
║    │                              ║   ┌─────────────────────────────────────────────────────────┐ ║                      │   ║
║    │                              ║   │                    CONNECTORS                           │ ║                      │   ║
║    │                              ║   │                                                         │ ║                      │   ║
║    │                              ║   │   PostgreSQL ◄──► MySQL ◄──► TiDB ◄──► Pinot ◄──► Hive │ ║                      │   ║
║    │                              ║   │       │            │          │          │         │    │ ║                      │   ║
║    │                              ║   │       └────────────┴──────────┴──────────┴─────────┘    │ ║                      │   ║
║    │                              ║   │                           │                             │ ║                      │   ║
║    │                              ║   │              UNIFIED SQL INTERFACE                      │ ║                      │   ║
║    │                              ║   └─────────────────────────────────────────────────────────┘ ║                      │   ║
║    │                              ║                                                               ║                      │   ║
║    │                              ║   Features:                                                   ║                      │   ║
║    │                              ║   • Query any data source with ANSI SQL                       ║                      │   ║
║    │                              ║   • Join across PostgreSQL, MySQL, TiDB, Pinot, Parquet       ║                      │   ║
║    │                              ║   • No data movement required                                 ║                      │   ║
║    │                              ║   • Role-based access control                                 ║                      │   ║
║    │                              ║                                                               ║                      │   ║
║    │                              ╚═══════════════════════════════════════════════════════════════╝                      │   ║
║    │                                                        │                                                            │   ║
║    └────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┘   ║
║                                                             │                                                                ║
║                         ┌───────────────────────────────────┼───────────────────────────────────┐                            ║
║                         │                                   │                                   │                            ║
║                         ▼                                   ▼                                   ▼                            ║
║    ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   ║
║    │                                       BUSINESS INTELLIGENCE LAYER                                                   │   ║
║    │                                                                                                                     │   ║
║    │   ┌─────────────────────────────┐   ┌─────────────────────────────┐   ┌─────────────────────────────┐              │   ║
║    │   │       📓 QUERYBOOK          │   │        📈 REDASH            │   │        📊 TABLEAU           │              │   ║
║    │   │   (Collaborative SQL IDE)   │   │   (Operational Dashboards)  │   │   (Enterprise Analytics)    │              │   ║
║    │   │                             │   │                             │   │                             │              │   ║
║    │   │  ┌───────────────────────┐  │   │  ┌───────────────────────┐  │   │  ┌───────────────────────┐  │              │   ║
║    │   │  │                       │  │   │  │                       │  │   │  │                       │  │              │   ║
║    │   │  │  👨‍💻 Data Engineers    │  │   │  │  📋 Product Managers  │  │   │  │  👔 C-Suite / Finance │  │              │   ║
║    │   │  │  👩‍🔬 Data Scientists   │  │   │  │  📊 Business Analysts │  │   │  │  ⚖️ Risk & Compliance │  │              │   ║
║    │   │  │  💻 Backend Developers │  │   │  │  🔧 Operations Team   │  │   │  │  📈 Strategy Team     │  │              │   ║
║    │   │  │                       │  │   │  │                       │  │   │  │                       │  │              │   ║
║    │   │  └───────────────────────┘  │   │  └───────────────────────┘  │   │  └───────────────────────┘  │              │   ║
║    │   │                             │   │                             │   │                             │              │   ║
║    │   │  Use Cases:                 │   │  Use Cases:                 │   │  Use Cases:                 │              │   ║
║    │   │  • Ad-hoc data exploration  │   │  • Transaction monitoring   │   │  • Revenue dashboards       │              │   ║
║    │   │  • Query collaboration      │   │  • Daily/weekly reports     │   │  • Regulatory reports       │              │   ║
║    │   │  • Data documentation       │   │  • Alerts & notifications   │   │  • Board presentations      │              │   ║
║    │   │  • Notebook-style analysis  │   │  • Self-service analytics   │   │  • Trend analysis           │              │   ║
║    │   │                             │   │                             │   │                             │              │   ║
║    │   └─────────────────────────────┘   └─────────────────────────────┘   └─────────────────────────────┘              │   ║
║    │                                                                                                                     │   ║
║    └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘   ║
║                                                                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                                              ║
║    DATA FLOW SUMMARY                                                                                                         ║
║    ═══════════════════                                                                                                       ║
║                                                                                                                              ║
║    ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  ║
║    │                                                                                                                      │  ║
║    │   1️⃣  OLTP WRITES     Microservices write to PostgreSQL (payments/wallets) and MySQL (users/merchants)              │  ║
║    │                                                                                                                      │  ║
║    │   2️⃣  CDC CAPTURE     Debezium captures PostgreSQL WAL changes, Maxwell captures MySQL binlog                        │  ║
║    │                                                                                                                      │  ║
║    │   3️⃣  EVENT STREAM    Both CDC tools publish change events to Apache Kafka topics                                    │  ║
║    │                                                                                                                      │  ║
║    │   4️⃣  FAN-OUT         Kafka consumers route data to three destinations:                                              │  ║
║    │                        • TiDB      → HTAP queries, real-time aggregations                                           │  ║
║    │                        • Pinot     → Sub-second analytics, live dashboards                                          │  ║
║    │                        • Data Lake → Parquet files for ML, compliance, historical                                   │  ║
║    │                                                                                                                      │  ║
║    │   5️⃣  QUERY LAYER     Trino provides federated SQL access across ALL data sources                                    │  ║
║    │                                                                                                                      │  ║
║    │   6️⃣  VISUALIZATION   BI tools connect to Trino/Pinot for different user personas                                    │  ║
║    │                                                                                                                      │  ║
║    └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                                                              ║
║    LATENCY TIERS                                                                                                             ║
║    ═════════════                                                                                                             ║
║                                                                                                                              ║
║    ⚡ REAL-TIME (100-500ms)     DB → Debezium/Maxwell → Kafka → Pinot → Redash Dashboard                                     ║
║    🔄 NEAR REAL-TIME (1-5s)     DB → CDC → Kafka → TiDB → Trino → Querybook                                                  ║
║    📦 BATCH (5-15 min)          DB → CDC → Kafka → Spark → Data Lake (Parquet) → Trino → Tableau                             ║
║                                                                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

## Quick Reference

| Layer | Components | Purpose |
|-------|------------|---------|
| **OLTP** | PostgreSQL, MySQL | Transactional databases per microservice |
| **CDC** | Debezium, Maxwell | Capture database changes in real-time |
| **Streaming** | Apache Kafka | Event bus connecting all components |
| **Processing** | TiDB, Pinot, Data Lake | Different query patterns & latencies |
| **Storage** | Apache Parquet | Columnar format for analytics |
| **Query** | Trino | Federated SQL across all sources |
| **BI** | Querybook, Redash, Tableau | Visualization for different personas |

