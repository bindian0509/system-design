# Fintech Payment Platform - Data Architecture System Design

## Overview
This document describes the end-to-end data architecture for a fintech payment organization, leveraging modern data tools for real-time analytics, batch processing, and business intelligence.

---

## System Design Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    FINTECH PAYMENT PLATFORM - DATA ARCHITECTURE                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         MICROSERVICES LAYER (OLTP)                                              │
│                                                                                                                 │
│   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐                    │
│   │  Payment Service │   │  Wallet Service  │   │   User Service   │   │ Merchant Service │                    │
│   │    (Spring Boot) │   │    (Go/gRPC)     │   │     (Node.js)    │   │    (Python)      │                    │
│   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘                    │
│            │                      │                      │                      │                               │
│            ▼                      ▼                      ▼                      ▼                               │
│   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐                    │
│   │   PostgreSQL     │   │   PostgreSQL     │   │     MySQL        │   │     MySQL        │                    │
│   │ (Transactions)   │   │   (Wallets)      │   │    (Users)       │   │  (Merchants)     │                    │
│   │                  │   │                  │   │                  │   │                  │                    │
│   │ • payments       │   │ • wallets        │   │ • users          │   │ • merchants      │                    │
│   │ • refunds        │   │ • balance_logs   │   │ • kyc_details    │   │ • settlements    │                    │
│   │ • disputes       │   │ • transactions   │   │ • auth_tokens    │   │ • mdr_config     │                    │
│   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘                    │
│            │                      │                      │                      │                               │
└────────────┼──────────────────────┼──────────────────────┼──────────────────────┼───────────────────────────────┘
             │                      │                      │                      │
             ▼                      ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CHANGE DATA CAPTURE (CDC) LAYER                                              │
│                                                                                                                 │
│   ┌────────────────────────────────────────┐       ┌────────────────────────────────────────┐                  │
│   │            DEBEZIUM                    │       │            MAXWELL                     │                  │
│   │      (for PostgreSQL DBs)              │       │       (for MySQL DBs)                  │                  │
│   │                                        │       │                                        │                  │
│   │  • Monitors WAL (Write-Ahead Log)      │       │  • Monitors MySQL binlog               │                  │
│   │  • Captures INSERT/UPDATE/DELETE       │       │  • Lightweight, low-latency            │                  │
│   │  • Schema evolution support            │       │  • JSON output format                  │                  │
│   │  • Exactly-once semantics              │       │  • Bootstrap support                   │                  │
│   └──────────────────┬─────────────────────┘       └──────────────────┬─────────────────────┘                  │
│                      │                                                │                                         │
│                      └────────────────────┬───────────────────────────┘                                         │
│                                           ▼                                                                     │
│                           ┌───────────────────────────────┐                                                     │
│                           │        APACHE KAFKA           │                                                     │
│                           │     (Event Streaming Hub)     │                                                     │
│                           │                               │                                                     │
│                           │  Topics:                      │                                                     │
│                           │  • cdc.payments.transactions  │                                                     │
│                           │  • cdc.wallets.balances       │                                                     │
│                           │  • cdc.users.profiles         │                                                     │
│                           │  • cdc.merchants.settlements  │                                                     │
│                           └───────────────┬───────────────┘                                                     │
│                                           │                                                                     │
└───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         DATA PROCESSING LAYER                                                   │
│                                                                                                                 │
│  ┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────────────────────────┐   │
│  │         TiDB            │   │     APACHE PINOT        │   │              DATA LAKE                      │   │
│  │    (HTAP Database)      │   │   (Real-time OLAP)      │   │         (Cloud Storage)                     │   │
│  │                         │   │                         │   │                                             │   │
│  │ Use Cases:              │   │ Use Cases:              │   │  ┌─────────────────────────────────────┐   │   │
│  │ • Real-time reporting   │   │ • Sub-second analytics  │   │  │     Apache Parquet Files            │   │   │
│  │ • HTAP workloads        │   │ • Dashboards (live)     │   │  │                                     │   │   │
│  │ • Horizontal scaling    │   │ • User-facing metrics   │   │  │  Partitioned by:                    │   │   │
│  │ • MySQL compatible      │   │ • Aggregations          │   │  │  • date / year / month              │   │   │
│  │                         │   │                         │   │  │  • entity_type                      │   │   │
│  │ Tables:                 │   │ Tables:                 │   │  │                                     │   │   │
│  │ • unified_transactions  │   │ • realtime_payments     │   │  │  Files:                             │   │   │
│  │ • aggregated_balances   │   │ • merchant_metrics      │   │  │  • payments/*.parquet               │   │   │
│  │ • settlement_ledger     │   │ • user_activity         │   │  │  • users/*.parquet                  │   │   │
│  │                         │   │ • fraud_scores          │   │  │  • merchants/*.parquet              │   │   │
│  │                         │   │                         │   │  │  • settlements/*.parquet            │   │   │
│  └─────────────────────────┘   └─────────────────────────┘   │  └─────────────────────────────────────┘   │   │
│                                                               │                                             │   │
│                                                               │  Storage: S3 / GCS / Azure Blob            │   │
│                                                               └─────────────────────────────────────────────┘   │
│                                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                    │                       │                       │
                    └───────────────────────┼───────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      FEDERATED QUERY LAYER                                                      │
│                                                                                                                 │
│                              ┌─────────────────────────────────────┐                                            │
│                              │              TRINO                  │                                            │
│                              │     (Distributed Query Engine)      │                                            │
│                              │                                     │                                            │
│                              │  Connectors:                        │                                            │
│                              │  ├── PostgreSQL Connector           │                                            │
│                              │  ├── MySQL Connector                │                                            │
│                              │  ├── TiDB Connector                 │                                            │
│                              │  ├── Pinot Connector                │                                            │
│                              │  ├── Hive/Parquet Connector         │                                            │
│                              │  └── Delta Lake Connector           │                                            │
│                              │                                     │                                            │
│                              │  Features:                          │                                            │
│                              │  • Federated queries across sources │                                            │
│                              │  • ANSI SQL support                 │                                            │
│                              │  • Query optimization               │                                            │
│                              │  • Access control                   │                                            │
│                              └──────────────────┬──────────────────┘                                            │
│                                                 │                                                               │
└─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    BUSINESS INTELLIGENCE LAYER                                                  │
│                                                                                                                 │
│   ┌─────────────────────────────┐   ┌─────────────────────────────┐   ┌─────────────────────────────┐          │
│   │         QUERYBOOK           │   │          REDASH             │   │         TABLEAU             │          │
│   │    (Collaborative SQL)      │   │    (Quick Dashboards)       │   │   (Enterprise Analytics)   │          │
│   │                             │   │                             │   │                             │          │
│   │  Users:                     │   │  Users:                     │   │  Users:                     │          │
│   │  • Data Engineers           │   │  • Product Managers         │   │  • C-Suite Executives       │          │
│   │  • Data Scientists          │   │  • Business Analysts        │   │  • Finance Team             │          │
│   │  • Backend Developers       │   │  • Operations Team          │   │  • Risk/Compliance          │          │
│   │                             │   │                             │   │                             │          │
│   │  Use Cases:                 │   │  Use Cases:                 │   │  Use Cases:                 │          │
│   │  • Ad-hoc exploration       │   │  • Daily transaction views  │   │  • Revenue reports          │          │
│   │  • Query collaboration      │   │  • Operational dashboards   │   │  • Regulatory reports       │          │
│   │  • Notebook-style analysis  │   │  • Alerts & monitoring      │   │  • Strategic insights       │          │
│   │  • Data documentation       │   │  • Self-service analytics   │   │  • Board presentations      │          │
│   │                             │   │                             │   │                             │          │
│   └─────────────────────────────┘   └─────────────────────────────┘   └─────────────────────────────┘          │
│                                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Data Flow

### 1. OLTP Layer (Microservices + Databases)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SERVICE-DATABASE MAPPING                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  POSTGRESQL (ACID-critical, complex queries)                    │
│  ├── Payment Service                                            │
│  │   └── payments, refunds, disputes, payment_methods           │
│  │                                                              │
│  └── Wallet Service                                             │
│      └── wallets, balance_logs, wallet_transactions             │
│                                                                 │
│  MYSQL (High read throughput, simpler schemas)                  │
│  ├── User Service                                               │
│  │   └── users, kyc_details, auth_tokens, sessions              │
│  │                                                              │
│  └── Merchant Service                                           │
│      └── merchants, settlements, mdr_config, terminals          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2. CDC Configuration

```yaml
# Debezium Connector Config (PostgreSQL)
{
  "name": "payments-pg-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "payments-db.internal",
    "database.port": "5432",
    "database.user": "debezium",
    "database.dbname": "payments",
    "database.server.name": "payments",
    "table.include.list": "public.payments,public.refunds,public.disputes",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_payments",
    "publication.name": "dbz_publication",
    "transforms": "route",
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "([^.]+)\\.([^.]+)\\.([^.]+)",
    "transforms.route.replacement": "cdc.$1.$3"
  }
}

# Maxwell Config (MySQL)
{
  "producer": "kafka",
  "kafka.bootstrap.servers": "kafka:9092",
  "kafka_topic": "cdc.%{database}.%{table}",
  "host": "users-db.internal",
  "user": "maxwell",
  "password": "***",
  "schema_database": "maxwell",
  "gtid_mode": true,
  "output_ddl": true
}
```

### 3. Data Routing Strategy

```
                              KAFKA TOPICS
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
    ┌──────────┐            ┌──────────┐            ┌──────────┐
    │   TiDB   │            │  Pinot   │            │Data Lake │
    │          │            │          │            │(Parquet) │
    └──────────┘            └──────────┘            └──────────┘
          │                        │                        │
    ┌─────┴─────┐            ┌─────┴─────┐          ┌───────┴───────┐
    │           │            │           │          │               │
    │ HTAP      │            │ Real-time │          │ Historical    │
    │ Queries   │            │ Analytics │          │ Analytics     │
    │           │            │           │          │ (Batch)       │
    │ • Reports │            │ • Live    │          │               │
    │ • Sync    │            │   metrics │          │ • ML Training │
    │   reads   │            │ • Alerts  │          │ • Auditing    │
    │           │            │           │          │ • Compliance  │
    └───────────┘            └───────────┘          └───────────────┘
```

---

## Component Responsibilities

### Why Each Tool?

| Component | Purpose | Why Chosen |
|-----------|---------|------------|
| **PostgreSQL** | Transactional data (payments, wallets) | ACID compliance, complex queries, JSON support |
| **MySQL** | User/Merchant data | High read throughput, mature ecosystem |
| **Debezium** | CDC for PostgreSQL | Native Kafka Connect, WAL-based, exactly-once |
| **Maxwell** | CDC for MySQL | Lightweight, low latency, simple setup |
| **Kafka** | Event streaming | Scalable, durable, decouples producers/consumers |
| **TiDB** | HTAP workloads | MySQL-compatible, horizontal scaling, real-time analytics |
| **Apache Pinot** | Real-time OLAP | Sub-second queries, user-facing analytics |
| **Data Lake + Parquet** | Cold storage | Cost-effective, columnar, ML/compliance workloads |
| **Trino** | Federated queries | Query any source with SQL, no data movement |
| **Querybook** | SQL collaboration | Notebooks for data teams, documentation |
| **Redash** | Operational dashboards | Quick setup, alerts, self-service |
| **Tableau** | Enterprise BI | Executive dashboards, advanced viz |

---

## Sample Use Cases

### Use Case 1: Real-time Fraud Detection Dashboard

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Payment    │────▶│  Debezium   │────▶│   Kafka     │────▶│   Pinot     │
│  Service    │     │   (CDC)     │     │             │     │ (Real-time) │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                                                                   ▼
                                                           ┌─────────────┐
                                                           │   Redash    │
                                                           │ (Dashboard) │
                                                           └─────────────┘

Query: SELECT merchant_id, COUNT(*) as failed_txns,
              AVG(amount) as avg_amount
       FROM realtime_payments
       WHERE status = 'FAILED'
         AND timestamp > ago('5m')
       GROUP BY merchant_id
       HAVING failed_txns > 10
```

### Use Case 2: Monthly Settlement Reconciliation

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Data Lake  │────▶│   Trino     │────▶│  Querybook  │────▶│  Finance    │
│  (Parquet)  │     │  (Query)    │     │  (Explore)  │     │   Team      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘

Query: SELECT m.merchant_name,
              SUM(p.amount) as total_volume,
              SUM(p.mdr_fee) as total_mdr,
              SUM(s.settled_amount) as total_settled
       FROM datalake.payments p
       JOIN datalake.merchants m ON p.merchant_id = m.id
       LEFT JOIN datalake.settlements s ON p.id = s.payment_id
       WHERE p.date BETWEEN '2025-11-01' AND '2025-11-30'
       GROUP BY m.merchant_name
```

### Use Case 3: Cross-System User Analytics

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRINO FEDERATED QUERY                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SELECT u.user_id, u.name, u.kyc_status,                       │
│         w.current_balance,                                      │
│         t.total_transactions,                                   │
│         t.total_volume                                          │
│  FROM mysql.users.users u                         ← MySQL       │
│  JOIN postgresql.wallets.wallets w                ← PostgreSQL  │
│       ON u.user_id = w.user_id                                  │
│  JOIN tidb.analytics.user_aggregates t            ← TiDB        │
│       ON u.user_id = t.user_id                                  │
│  WHERE t.total_volume > 100000                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Latencies

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         END-TO-END LATENCIES                              │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  SOURCE DB ──▶ CDC ──▶ KAFKA ──▶ DESTINATION                              │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │ Path                              │ Latency        │ Use Case       │ │
│  ├───────────────────────────────────┼────────────────┼────────────────│ │
│  │ DB → Debezium → Kafka → Pinot     │ ~100-500ms     │ Real-time dash │ │
│  │ DB → Maxwell → Kafka → Pinot      │ ~50-200ms      │ Live metrics   │ │
│  │ DB → CDC → Kafka → TiDB           │ ~500ms-2s      │ HTAP queries   │ │
│  │ DB → CDC → Kafka → Data Lake      │ 5-15 minutes   │ Batch/ML       │ │
│  │ Data Lake → Trino → BI Tool       │ 2-30 seconds   │ Ad-hoc queries │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              KUBERNETES CLUSTER                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      NAMESPACE: fintech-oltp                         │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ │   │
│  │  │ Payment Svc  │ │ Wallet Svc   │ │ User Svc     │ │Merchant Svc │ │   │
│  │  │ (3 replicas) │ │ (3 replicas) │ │ (5 replicas) │ │(3 replicas) │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      NAMESPACE: fintech-cdc                          │   │
│  │  ┌─────────────────────────────┐ ┌─────────────────────────────┐    │   │
│  │  │  Debezium Connect Cluster   │ │    Maxwell Daemons          │    │   │
│  │  │  (Kafka Connect Workers)    │ │    (per MySQL instance)     │    │   │
│  │  └─────────────────────────────┘ └─────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      NAMESPACE: fintech-analytics                    │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │ Pinot        │ │ TiDB         │ │ Trino        │                 │   │
│  │  │ Cluster      │ │ Cluster      │ │ Cluster      │                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      NAMESPACE: fintech-bi                           │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │ Querybook    │ │ Redash       │ │ Tableau      │                 │   │
│  │  │ (Self-host)  │ │ (Self-host)  │ │ Server       │                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           MANAGED SERVICES                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ AWS RDS      │ │ Confluent    │ │ AWS S3       │ │ TiDB Cloud   │       │
│  │ (PG/MySQL)   │ │ Kafka        │ │ (Data Lake)  │ │ (Optional)   │       │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

This architecture provides:

1. **Real-time Capabilities**: CDC → Kafka → Pinot pipeline delivers sub-second analytics
2. **HTAP Workloads**: TiDB handles both transactional sync and analytical queries
3. **Cost-Effective Storage**: Parquet files in Data Lake for historical/compliance data
4. **Federated Access**: Trino enables cross-system queries without data movement
5. **Multi-Persona BI**: Different tools for different user needs (engineers, analysts, executives)

The design follows the **Lambda Architecture** pattern with:
- **Speed Layer**: Pinot for real-time
- **Batch Layer**: Data Lake + Parquet
- **Serving Layer**: Trino + BI Tools

