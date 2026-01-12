# Data Storage Strategies

Choosing the right database and storage strategy is one of the most critical decisions in system design. This guide covers database types, indexing strategies, partitioning, and when to use each.

## Database Selection Framework

```mermaid
flowchart TB
    Start[Start] --> Q1{What's your data model?}

    Q1 -->|Structured, relational| SQL[SQL Database]
    Q1 -->|Semi-structured, flexible| Document[Document Store]
    Q1 -->|Key-value pairs| KV[Key-Value Store]
    Q1 -->|Time-series| TS[Time-Series DB]
    Q1 -->|Graph relationships| Graph[Graph Database]
    Q1 -->|Text search| Search[Search Engine]

    SQL --> Q2{Scale requirement?}
    Q2 -->|Single node OK| PostgreSQL[PostgreSQL / MySQL]
    Q2 -->|Distributed needed| NewSQL[CockroachDB / Spanner]

    Document --> MongoDB[MongoDB / Couchbase]
    KV --> Q3{Persistence needed?}
    Q3 -->|Yes| DynamoDB[DynamoDB / Redis]
    Q3 -->|No, cache only| Memcached[Memcached / Redis]

    TS --> InfluxDB[InfluxDB / TimescaleDB]
    Graph --> Neo4j[Neo4j / Neptune]
    Search --> Elasticsearch[Elasticsearch / Solr]
```

---

## SQL vs NoSQL

### Comparison Table

| Aspect | SQL | NoSQL |
|--------|-----|-------|
| **Data Model** | Tables with rows | Varies (document, key-value, etc.) |
| **Schema** | Fixed, predefined | Flexible, dynamic |
| **Transactions** | ACID | Usually BASE |
| **Scaling** | Vertical (traditionally) | Horizontal (designed for) |
| **Joins** | Native support | Limited or none |
| **Query Language** | Standardized SQL | Varies by database |
| **Best For** | Complex queries, transactions | Scale, flexibility, specific access patterns |

### When to Choose SQL

```mermaid
flowchart TB
    SQL[Choose SQL When] --> A[Complex relationships]
    SQL --> B[ACID transactions required]
    SQL --> C[Ad-hoc queries needed]
    SQL --> D[Data integrity critical]
    SQL --> E[Reporting requirements]
```

**Examples:**
- Banking systems (transactions)
- E-commerce orders (relationships)
- ERP systems (complex queries)
- Inventory management (consistency)

### When to Choose NoSQL

```mermaid
flowchart TB
    NoSQL[Choose NoSQL When] --> A[Massive scale]
    NoSQL --> B[Flexible schema]
    NoSQL --> C[High write throughput]
    NoSQL --> D[Specific access patterns]
    NoSQL --> E[Geographic distribution]
```

**Examples:**
- Social media feeds (scale)
- Product catalogs (flexible schema)
- IoT sensor data (high write volume)
- Session storage (key-value access)

---

## Database Types Deep Dive

### 1. Relational Databases (SQL)

**Architecture:**

```mermaid
flowchart TB
    subgraph sql [SQL Database Architecture]
        Query[Query Parser] --> Optimizer[Query Optimizer]
        Optimizer --> Executor[Executor]
        Executor --> Buffer[Buffer Pool]
        Buffer --> Storage[Disk Storage]

        WAL[Write-Ahead Log] --> Storage
    end
```

**Key Features:**
- ACID transactions
- Rich query language (SQL)
- Indexes (B-tree, hash)
- Foreign key constraints
- Views, stored procedures

**Popular Options:**

| Database | Best For | Key Feature |
|----------|----------|-------------|
| **PostgreSQL** | General purpose, complex queries | Extensions, JSON support |
| **MySQL** | Web applications | Replication, InnoDB |
| **SQL Server** | Enterprise, Windows | Integration with Microsoft |
| **Oracle** | Enterprise, mission-critical | Advanced features |

### 2. Document Databases

Store data as JSON-like documents.

```mermaid
flowchart LR
    subgraph doc [Document Structure]
        Doc["
        {
          _id: '123',
          name: 'John',
          orders: [
            { item: 'Book', qty: 2 },
            { item: 'Pen', qty: 5 }
          ],
          address: {
            city: 'NYC',
            zip: '10001'
          }
        }
        "]
    end
```

**When to Use:**
- Variable schemas
- Hierarchical data
- Content management
- Catalogs with varying attributes

**Popular Options:**

| Database | Best For | Key Feature |
|----------|----------|-------------|
| **MongoDB** | General document storage | Flexible queries, aggregation |
| **Couchbase** | High performance | Memory-first, mobile sync |
| **CouchDB** | Offline-first apps | Master-master replication |

### 3. Key-Value Stores

Simplest model: key → value.

```mermaid
flowchart LR
    Key1[user:123] --> Value1["{ name: 'John', age: 30 }"]
    Key2[session:abc] --> Value2["{ token: 'xyz', expiry: '...' }"]
    Key3[cache:product:456] --> Value3["{ title: 'Widget', price: 9.99 }"]
```

**When to Use:**
- Caching
- Session storage
- Shopping carts
- Real-time data

**Popular Options:**

| Database | Best For | Key Feature |
|----------|----------|-------------|
| **Redis** | Caching, real-time | Data structures, pub/sub |
| **Memcached** | Simple caching | Multi-threaded |
| **DynamoDB** | Serverless, scalable | Managed, predictable performance |

### 4. Column-Family Databases

Optimized for writes and column-based access.

```mermaid
flowchart TB
    subgraph cf [Column Family Structure]
        Row1[Row Key: user123]

        subgraph cf1 [Profile CF]
            C1[name: John]
            C2[email: john@example.com]
        end

        subgraph cf2 [Activity CF]
            C3[last_login: 2024-01-15]
            C4[login_count: 42]
        end

        Row1 --> cf1
        Row1 --> cf2
    end
```

**When to Use:**
- Time-series data
- High write throughput
- Data that's rarely updated
- Analytics workloads

**Popular Options:**

| Database | Best For | Key Feature |
|----------|----------|-------------|
| **Cassandra** | High availability, writes | Tunable consistency |
| **HBase** | Hadoop integration | Strong consistency |
| **ScyllaDB** | Cassandra-compatible, faster | C++ implementation |

### 5. Graph Databases

Nodes and relationships as first-class citizens.

```mermaid
flowchart LR
    subgraph graph [Graph Data Model]
        User1((Alice)) -->|FRIENDS_WITH| User2((Bob))
        User2 -->|LIKES| Product1[Widget]
        User1 -->|PURCHASED| Product1
        User1 -->|FRIENDS_WITH| User3((Carol))
        User3 -->|LIKES| Product1
    end
```

**When to Use:**
- Social networks
- Recommendation engines
- Fraud detection
- Knowledge graphs

**Popular Options:**

| Database | Best For | Key Feature |
|----------|----------|-------------|
| **Neo4j** | General graph workloads | Cypher query language |
| **Amazon Neptune** | Managed, multi-model | Gremlin, SPARQL |
| **TigerGraph** | Real-time analytics | Parallel processing |

### 6. Time-Series Databases

Optimized for timestamped data.

```mermaid
flowchart TB
    subgraph ts [Time-Series Data]
        T1[2024-01-01 00:00:00, cpu=45.2]
        T2[2024-01-01 00:00:01, cpu=46.1]
        T3[2024-01-01 00:00:02, cpu=44.8]
        T4[...]
    end
```

**When to Use:**
- Metrics and monitoring
- IoT sensor data
- Financial tick data
- Application logs

**Popular Options:**

| Database | Best For | Key Feature |
|----------|----------|-------------|
| **InfluxDB** | General time-series | Flux query language |
| **TimescaleDB** | PostgreSQL compatibility | SQL interface |
| **Prometheus** | Metrics | Pull-based collection |

---

## Indexing Strategies

### Index Types

```mermaid
flowchart TB
    subgraph indexes [Index Types]
        Btree[B-Tree Index<br/>Range queries]
        Hash[Hash Index<br/>Exact matches]
        GIN[GIN Index<br/>Full-text, arrays]
        Bitmap[Bitmap Index<br/>Low cardinality]
    end
```

| Index Type | Best For | Example Query |
|------------|----------|---------------|
| **B-Tree** | Range queries, ordering | `WHERE age > 25 ORDER BY age` |
| **Hash** | Exact equality | `WHERE id = 123` |
| **GIN** | Full-text search, JSON | `WHERE tags @> '["tech"]'` |
| **GiST** | Geometric, full-text | `WHERE location <@ box` |
| **BRIN** | Large sequential data | `WHERE created_at > '2024-01-01'` |

### B-Tree vs LSM-Tree

```mermaid
flowchart TB
    subgraph btree [B-Tree - Read Optimized]
        direction TB
        Root[Root Node]
        L1[Internal Nodes]
        Leaf[Leaf Nodes - Sorted]
        Root --> L1 --> Leaf
    end

    subgraph lsm [LSM-Tree - Write Optimized]
        direction TB
        Memtable[Memtable - In Memory]
        L0[Level 0 SSTable]
        L1LSM[Level 1 SSTable]
        L2[Level 2 SSTable]
        Memtable -->|Flush| L0
        L0 -->|Compact| L1LSM
        L1LSM -->|Compact| L2
    end
```

| Aspect | B-Tree | LSM-Tree |
|--------|--------|----------|
| **Writes** | Slower (in-place update) | Faster (append-only) |
| **Reads** | Faster (single lookup) | Slower (multiple levels) |
| **Space** | More efficient | Write amplification |
| **Use Case** | OLTP, reads | High write throughput |
| **Examples** | PostgreSQL, MySQL | Cassandra, RocksDB, LevelDB |

### Indexing Best Practices

```sql
-- 1. Index columns used in WHERE, JOIN, ORDER BY
CREATE INDEX idx_users_email ON users(email);

-- 2. Composite indexes for multi-column queries
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at DESC);

-- 3. Partial indexes for specific conditions
CREATE INDEX idx_active_users ON users(email) WHERE status = 'active';

-- 4. Covering indexes to avoid table lookups
CREATE INDEX idx_orders_cover ON orders(user_id) INCLUDE (total, status);
```

**Common Mistakes:**
- Over-indexing (slows writes)
- Wrong column order in composite index
- Not considering query patterns
- Ignoring index maintenance

---

## Data Partitioning

### Horizontal Partitioning (Sharding)

Split data across multiple databases by rows.

```mermaid
flowchart TB
    App[Application] --> Router[Shard Router]

    Router -->|Users A-M| Shard1[(Shard 1)]
    Router -->|Users N-Z| Shard2[(Shard 2)]
```

#### Partitioning Strategies

| Strategy | How It Works | Pros | Cons |
|----------|--------------|------|------|
| **Range** | By value range (A-M, N-Z) | Easy range queries | Hot spots |
| **Hash** | hash(key) % shards | Even distribution | No range queries |
| **List** | By explicit values | Predictable | Manual management |
| **Composite** | Combination | Flexible | Complex |

### Vertical Partitioning

Split data by columns into different tables/databases.

```mermaid
flowchart LR
    subgraph before [Before - Wide Table]
        Full[Users: id, name, email, bio, avatar, settings, preferences]
    end

    subgraph after [After - Vertical Split]
        Core[Core: id, name, email]
        Profile[Profile: id, bio, avatar]
        Prefs[Prefs: id, settings, preferences]
    end
```

**When to Use:**
- Different access patterns
- Large columns rarely accessed
- Different storage requirements

### Partitioning in PostgreSQL

```sql
-- Range partitioning by date
CREATE TABLE orders (
    id BIGINT,
    created_at TIMESTAMP,
    amount DECIMAL
) PARTITION BY RANGE (created_at);

CREATE TABLE orders_2024_q1 PARTITION OF orders
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');

CREATE TABLE orders_2024_q2 PARTITION OF orders
    FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');

-- Hash partitioning
CREATE TABLE users (
    id BIGINT,
    email TEXT
) PARTITION BY HASH (id);

CREATE TABLE users_p0 PARTITION OF users
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE users_p1 PARTITION OF users
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);
```

---

## Replication Strategies

### Synchronous vs Asynchronous

```mermaid
sequenceDiagram
    participant Client
    participant Primary
    participant Replica

    rect rgb(200, 230, 200)
        Note over Client,Replica: Synchronous Replication
        Client->>Primary: Write
        Primary->>Replica: Replicate
        Replica-->>Primary: ACK
        Primary-->>Client: Success
    end

    rect rgb(230, 200, 200)
        Note over Client,Replica: Asynchronous Replication
        Client->>Primary: Write
        Primary-->>Client: Success
        Primary->>Replica: Replicate (async)
    end
```

| Aspect | Synchronous | Asynchronous |
|--------|-------------|--------------|
| **Latency** | Higher (wait for replica) | Lower |
| **Durability** | Guaranteed | Risk of data loss |
| **Availability** | Lower (replica failure blocks) | Higher |
| **Use Case** | Financial data | General use |

### Replication Topologies

```mermaid
flowchart TB
    subgraph single [Single Leader]
        L1[(Leader)] --> F1[(Follower)]
        L1 --> F2[(Follower)]
    end

    subgraph multi [Multi-Leader]
        ML1[(Leader 1)] <--> ML2[(Leader 2)]
        ML1 --> MF1[(Follower)]
        ML2 --> MF2[(Follower)]
    end

    subgraph leaderless [Leaderless]
        N1[(Node 1)] <--> N2[(Node 2)]
        N2 <--> N3[(Node 3)]
        N3 <--> N1
    end
```

---

## Storage Engine Internals

### Write Path (LSM-Based)

```mermaid
flowchart TB
    Write[Write Request] --> WAL[Write-Ahead Log]
    WAL --> Memtable[Memtable - In Memory]
    Memtable -->|Full| Flush[Flush to Disk]
    Flush --> SSTable[SSTable - Sorted String Table]
    SSTable --> Compaction[Background Compaction]
    Compaction --> Merged[Merged SSTables]
```

### Read Path

```mermaid
flowchart TB
    Read[Read Request] --> Bloom[Bloom Filter Check]
    Bloom -->|Might exist| Memtable[Check Memtable]
    Memtable -->|Not found| L0[Check L0 SSTables]
    L0 -->|Not found| L1[Check L1 SSTables]
    L1 -->|Not found| LN[Check LN SSTables]
    Bloom -->|Definitely not| NotFound[Return Not Found]
```

### Write-Ahead Logging (WAL)

```mermaid
flowchart LR
    Write[Write] --> WAL[WAL - Sequential Write]
    WAL --> Memory[Update Memory]
    Memory --> Response[Return Success]

    WAL -.->|Async| Disk[Disk Persistence]
```

**Purpose:**
- Durability before data reaches main storage
- Crash recovery
- Replication log

---

## Polyglot Persistence

Use different databases for different needs.

```mermaid
flowchart TB
    subgraph app [Application]
        API[API Layer]
    end

    subgraph databases [Data Stores]
        PostgreSQL[(PostgreSQL<br/>Orders, Users)]
        Redis[(Redis<br/>Sessions, Cache)]
        Elasticsearch[(Elasticsearch<br/>Product Search)]
        S3[S3<br/>Images, Files]
        Cassandra[(Cassandra<br/>Activity Logs)]
    end

    API --> PostgreSQL
    API --> Redis
    API --> Elasticsearch
    API --> S3
    API --> Cassandra
```

### Example: E-commerce Platform

| Data Type | Database | Reason |
|-----------|----------|--------|
| **Users, Orders** | PostgreSQL | ACID transactions |
| **Product Catalog** | MongoDB | Flexible schema |
| **Product Search** | Elasticsearch | Full-text search |
| **Sessions** | Redis | Fast access |
| **Activity Stream** | Cassandra | High write volume |
| **Product Images** | S3 | Blob storage |

---

## Schema Design Patterns

### 1. Normalization vs Denormalization

```mermaid
flowchart LR
    subgraph normalized [Normalized]
        Users1[Users]
        Orders1[Orders]
        Products1[Products]
        OrderItems1[Order Items]

        Orders1 -->|FK| Users1
        OrderItems1 -->|FK| Orders1
        OrderItems1 -->|FK| Products1
    end

    subgraph denormalized [Denormalized]
        Orders2["Orders (with user_name, product_name embedded)"]
    end
```

| Approach | Pros | Cons |
|----------|------|------|
| **Normalized** | No redundancy, data integrity | More joins, slower reads |
| **Denormalized** | Faster reads, simpler queries | Data duplication, update anomalies |

### 2. Soft Deletes

```sql
-- Instead of DELETE
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE users ADD COLUMN is_deleted BOOLEAN DEFAULT false;

-- "Delete" by marking
UPDATE users SET is_deleted = true, deleted_at = NOW() WHERE id = 123;

-- Query active users
SELECT * FROM users WHERE is_deleted = false;
```

### 3. Audit Trail

```sql
CREATE TABLE user_audit (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    action VARCHAR(20),  -- INSERT, UPDATE, DELETE
    old_data JSONB,
    new_data JSONB,
    changed_by BIGINT,
    changed_at TIMESTAMP DEFAULT NOW()
);
```

---

## Database Selection Cheat Sheet

### By Use Case

| Use Case | Primary Choice | Alternatives |
|----------|----------------|--------------|
| **General Web App** | PostgreSQL | MySQL |
| **High Traffic Caching** | Redis | Memcached |
| **Document Storage** | MongoDB | Couchbase |
| **Analytics** | ClickHouse | BigQuery |
| **Time-Series** | TimescaleDB | InfluxDB |
| **Search** | Elasticsearch | Solr, Meilisearch |
| **Graph Data** | Neo4j | Neptune |
| **High Write Volume** | Cassandra | ScyllaDB |

### By Scale

| Scale | Recommendation |
|-------|----------------|
| **MVP/Startup** | PostgreSQL for everything |
| **Growing** | PostgreSQL + Redis cache |
| **Scale** | Sharded PostgreSQL + Redis Cluster + Elasticsearch |
| **Massive** | Polyglot with specialized DBs per workload |

---

## Summary

1. **Choose based on access patterns** - Not just data model
2. **Start simple** - PostgreSQL handles most use cases
3. **Add specialized DBs as needed** - Polyglot persistence
4. **Index wisely** - Understand B-tree vs LSM trade-offs
5. **Plan for scale** - Design partitioning early
6. **Consider operational complexity** - Each DB adds overhead

---

**Previous**: [← Distributed System Concepts](05-distributed-system-concepts.md) | **Next**: [Caching Strategies →](07-caching-strategies.md)
