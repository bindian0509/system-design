# E-Commerce Browsing System - Architecture Diagrams

> **Rendering Instructions**: These Mermaid diagrams can be rendered as images using:
> - [Mermaid Live Editor](https://mermaid.live/) - Copy/paste diagrams
> - VS Code with "Markdown Preview Mermaid Support" extension
> - GitHub - Renders automatically in markdown files
> - [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) - `mmdc -i input.md -o output.png`

---

## 1. Complete System Architecture (Bird's Eye View)

```mermaid
flowchart TB
    subgraph internet [Internet]
        Users[("👥 Users<br/>1M+ DAU")]
        CDN[("🌐 CDN<br/>CloudFlare/Fastly")]
    end

    subgraph edge [Edge Layer]
        WAF["🛡️ WAF<br/>Web Application Firewall"]
        GLB["⚖️ Global Load Balancer<br/>DNS-based routing"]
    end

    subgraph ingress [Ingress Layer]
        LB1["Load Balancer 1<br/>Nginx"]
        LB2["Load Balancer 2<br/>Nginx"]
        LB3["Load Balancer 3<br/>Nginx"]
    end

    subgraph api_gateway [API Gateway Cluster]
        Kong1["Kong Gateway 1"]
        Kong2["Kong Gateway 2"]
        Kong3["Kong Gateway 3"]
    end

    subgraph api_servers [API Server Fleet - Kubernetes]
        API1["API Server 1<br/>Go/Rust"]
        API2["API Server 2<br/>Go/Rust"]
        API3["API Server 3<br/>Go/Rust"]
        API4["API Server 4<br/>Go/Rust"]
        APIn["... API Server N"]
    end

    subgraph core_services [Core Microservices]
        BrowseSvc["📦 Browse Service<br/>Product listing & filtering"]
        RankingSvc["📊 Ranking Service<br/>Score merging & sorting"]
        PersonalizationSvc["👤 Personalization Service<br/>User-specific ranking"]
        EventCollector["📡 Event Collector<br/>Clickstream ingestion"]
    end

    subgraph cache_layer [Cache Layer - Redis Cluster]
        direction LR
        Redis1[("Redis Primary 1")]
        Redis2[("Redis Primary 2")]
        Redis3[("Redis Primary 3")]
        RedisR1[("Replica 1")]
        RedisR2[("Replica 2")]
        RedisR3[("Replica 3")]
    end

    subgraph database_layer [Database Layer - PostgreSQL]
        PGPrimary[("PostgreSQL Primary<br/>Writes")]
        PGReplica1[("Read Replica 1")]
        PGReplica2[("Read Replica 2")]
        PGReplica3[("Read Replica 3")]
        PgBouncer["PgBouncer<br/>Connection Pool"]
    end

    subgraph streaming [Streaming Platform - Kafka]
        direction LR
        Broker1["Kafka Broker 1"]
        Broker2["Kafka Broker 2"]
        Broker3["Kafka Broker 3"]
        Broker4["Kafka Broker 4"]
        Broker5["Kafka Broker 5"]
        ZK["ZooKeeper<br/>Cluster"]
    end

    subgraph realtime_processing [Real-Time Processing - Flink]
        FlinkJM["Flink JobManager"]
        FlinkTM1["TaskManager 1"]
        FlinkTM2["TaskManager 2"]
        FlinkTM3["TaskManager 3"]
        FlinkTM4["TaskManager 4"]
    end

    subgraph batch_processing [Batch Processing]
        Airflow["Apache Airflow<br/>Scheduler"]
        SparkMaster["Spark Master"]
        SparkW1["Spark Worker 1"]
        SparkW2["Spark Worker 2"]
        SparkWn["... Worker N"]
    end

    subgraph storage [Data Lake]
        MinIO[("MinIO / S3<br/>Object Storage")]
        Parquet["📁 Parquet Files<br/>Partitioned by date"]
    end

    subgraph observability [Observability Stack]
        Prometheus["Prometheus<br/>Metrics"]
        Grafana["Grafana<br/>Dashboards"]
        Jaeger["Jaeger<br/>Tracing"]
        Loki["Loki<br/>Logs"]
        AlertMgr["AlertManager"]
    end

    %% User Flow
    Users --> CDN
    CDN --> WAF
    WAF --> GLB
    GLB --> LB1 & LB2 & LB3
    LB1 & LB2 & LB3 --> Kong1 & Kong2 & Kong3
    Kong1 & Kong2 & Kong3 --> API1 & API2 & API3 & API4 & APIn

    %% API to Services
    API1 & API2 & API3 & API4 --> BrowseSvc
    API1 & API2 & API3 & API4 --> PersonalizationSvc
    API1 & API2 & API3 & API4 --> EventCollector
    BrowseSvc --> RankingSvc

    %% Services to Cache
    BrowseSvc --> Redis1 & Redis2 & Redis3
    RankingSvc --> Redis1 & Redis2 & Redis3
    PersonalizationSvc --> Redis1 & Redis2 & Redis3
    Redis1 --> RedisR1
    Redis2 --> RedisR2
    Redis3 --> RedisR3

    %% Services to Database
    BrowseSvc --> PgBouncer
    PersonalizationSvc --> PgBouncer
    PgBouncer --> PGPrimary
    PgBouncer --> PGReplica1 & PGReplica2 & PGReplica3
    PGPrimary --> PGReplica1 & PGReplica2 & PGReplica3

    %% Event Flow
    EventCollector --> Broker1 & Broker2 & Broker3
    Broker1 & Broker2 & Broker3 --> ZK
    Broker4 & Broker5 --> ZK

    %% Real-time Processing
    Broker1 & Broker2 --> FlinkJM
    FlinkJM --> FlinkTM1 & FlinkTM2 & FlinkTM3 & FlinkTM4
    FlinkTM1 & FlinkTM2 --> Redis1 & Redis2

    %% Batch Processing
    Broker3 --> MinIO
    MinIO --> Parquet
    Airflow --> SparkMaster
    SparkMaster --> SparkW1 & SparkW2 & SparkWn
    Parquet --> SparkW1 & SparkW2
    SparkW1 & SparkW2 --> PGPrimary
    SparkW1 & SparkW2 --> Redis1 & Redis2

    %% Observability
    API1 & API2 --> Prometheus
    BrowseSvc & RankingSvc --> Prometheus
    FlinkJM --> Prometheus
    Prometheus --> Grafana
    Prometheus --> AlertMgr
    API1 & API2 --> Jaeger
    API1 & API2 --> Loki
```

---

## 2. Detailed Data Flow - Browse Request

```mermaid
flowchart LR
    subgraph client [Client Application]
        Browser["🌐 Browser/App"]
    end

    subgraph request_flow [Request Processing]
        direction TB
        LB["Load Balancer"]
        Gateway["API Gateway<br/>Rate Limit + Auth"]
        API["API Server"]
    end

    subgraph service_layer [Service Layer]
        direction TB
        Browse["Browse Service"]
        Ranking["Ranking Service"]
        Personalization["Personalization<br/>Service"]
    end

    subgraph cache [Redis Cache]
        direction TB
        PopCache[("Popularity<br/>Sorted Set")]
        HotCache[("Hot Items<br/>Sorted Set")]
        UserCache[("User Features<br/>Hash")]
        ProductCache[("Product Details<br/>Hash")]
    end

    subgraph db [PostgreSQL]
        direction TB
        ProductTable[("Products<br/>Table")]
        PopTable[("Popularity<br/>Table")]
        UserTable[("User Profiles<br/>Table")]
    end

    subgraph response_flow [Response Assembly]
        Merger["Result Merger"]
        Formatter["Response<br/>Formatter"]
    end

    %% Request flow
    Browser -->|"1. GET /browse"| LB
    LB -->|"2. Route"| Gateway
    Gateway -->|"3. Validate"| API
    API -->|"4. Dispatch"| Browse

    %% Cache reads (parallel)
    Browse -->|"5a. Get popular IDs"| PopCache
    Browse -->|"5b. Get hot IDs"| HotCache

    %% Personalization
    Browse -->|"6. Get user context"| Personalization
    Personalization -->|"7. Fetch features"| UserCache
    UserCache -.->|"miss"| UserTable

    %% Product details
    Browse -->|"8. Fetch products"| ProductCache
    ProductCache -.->|"miss"| ProductTable

    %% Ranking
    Browse -->|"9. Merge scores"| Ranking
    Ranking -->|"10. Apply rules"| Merger

    %% Response
    Merger -->|"11. Format"| Formatter
    Formatter -->|"12. JSON"| API
    API -->|"13. Response"| Browser

    style Browser fill:#e1f5fe
    style Formatter fill:#c8e6c9
```

---

## 3. Event Ingestion & Processing Pipeline

```mermaid
flowchart TB
    subgraph clients [Client Events]
        Web["🌐 Web App"]
        iOS["📱 iOS App"]
        Android["📱 Android App"]
    end

    subgraph collection [Event Collection Layer]
        Collector1["Event Collector 1"]
        Collector2["Event Collector 2"]
        Collector3["Event Collector 3"]
        CollectorLB["Collector LB"]
    end

    subgraph validation [Event Processing]
        Validator["Event Validator<br/>Schema validation"]
        Enricher["Event Enricher<br/>Add metadata"]
        Router["Event Router<br/>Topic selection"]
    end

    subgraph kafka [Kafka Cluster]
        direction TB
        Topic1["📨 user-events<br/>64 partitions"]
        Topic2["📨 page-views<br/>32 partitions"]
        Topic3["📨 cart-events<br/>16 partitions"]
        SchemaReg["Schema Registry"]
    end

    subgraph consumers [Consumer Groups]
        direction TB
        FlinkConsumer["Flink Consumer<br/>Hot Items"]
        S3Consumer["S3 Sink Connector<br/>Data Lake"]
        ProfileConsumer["Profile Updater<br/>User features"]
    end

    subgraph realtime [Real-Time Processing]
        direction TB
        FlinkApp["Flink Application"]
        Window5m["5-min Window<br/>Aggregator"]
        Window1h["1-hour Window<br/>Trend Detector"]
        HotScorer["Hot Score<br/>Calculator"]
    end

    subgraph datalake [Data Lake]
        direction TB
        RawEvents[("Raw Events<br/>Parquet")]
        Partitioned["📁 Partitioned by<br/>year/month/day/hour"]
    end

    subgraph output [Output Destinations]
        RedisHot[("Redis<br/>hot_items:*")]
        Alerts["🚨 Alerts<br/>PagerDuty"]
        Metrics["📊 Metrics<br/>Prometheus"]
    end

    %% Event flow
    Web & iOS & Android -->|"HTTP POST"| CollectorLB
    CollectorLB --> Collector1 & Collector2 & Collector3
    Collector1 & Collector2 & Collector3 --> Validator
    Validator --> Enricher
    Enricher --> Router
    Router --> Topic1 & Topic2 & Topic3
    Topic1 & Topic2 & Topic3 --> SchemaReg

    %% Consumer flow
    Topic1 --> FlinkConsumer
    Topic1 --> S3Consumer
    Topic1 --> ProfileConsumer

    %% Real-time processing
    FlinkConsumer --> FlinkApp
    FlinkApp --> Window5m
    FlinkApp --> Window1h
    Window5m --> HotScorer
    Window1h --> HotScorer
    HotScorer --> RedisHot
    HotScorer -->|"score > 5.0"| Alerts
    FlinkApp --> Metrics

    %% Data lake
    S3Consumer --> RawEvents
    RawEvents --> Partitioned

    style FlinkApp fill:#fff3e0
    style RedisHot fill:#ffcdd2
```

---

## 4. Batch Pipeline - Popularity Computation

```mermaid
flowchart TB
    subgraph schedule [Scheduling]
        Airflow["🕐 Apache Airflow<br/>Daily 2:00 AM UTC"]
        DAG["popularity_pipeline DAG"]
    end

    subgraph sensors [Pre-conditions]
        DataSensor["📡 Data Sensor<br/>Wait for complete data"]
        ResourceCheck["🔍 Resource Check<br/>Cluster health"]
    end

    subgraph spark_cluster [Spark Cluster]
        SparkDriver["Spark Driver"]
        Executor1["Executor 1<br/>8GB RAM"]
        Executor2["Executor 2<br/>8GB RAM"]
        Executor3["Executor 3<br/>8GB RAM"]
        ExecutorN["... Executor N"]
    end

    subgraph data_sources [Data Sources]
        DataLake[("📁 Data Lake<br/>30 days events")]
        ProductMaster[("📦 Product Master<br/>Active products")]
        HistoricalScores[("📈 Previous Scores<br/>For delta calc")]
    end

    subgraph processing [Processing Steps]
        direction TB
        Step1["1️⃣ Load Events<br/>Filter last 30 days"]
        Step2["2️⃣ Apply Decay<br/>exp(-0.1 × days_ago)"]
        Step3["3️⃣ Compute Weights<br/>view=1, click=3, cart=10"]
        Step4["4️⃣ Aggregate Scores<br/>Group by product_id"]
        Step5["5️⃣ Compute Ranks<br/>Global ordering"]
        Step6["6️⃣ Category Ranks<br/>Per-category ordering"]
    end

    subgraph outputs [Output Destinations]
        PopTable[("🗄️ PostgreSQL<br/>product_popularity")]
        CatPopTable[("🗄️ PostgreSQL<br/>category_popularity")]
        RedisGlobal[("🔴 Redis<br/>popularity:global")]
        RedisCat[("🔴 Redis<br/>popularity:category:*")]
    end

    subgraph validation [Post-processing]
        Validator["✅ Data Validator<br/>Quality checks"]
        Notifier["📧 Notifier<br/>Slack/Email"]
        Metrics["📊 Job Metrics<br/>Duration, counts"]
    end

    %% Flow
    Airflow --> DAG
    DAG --> DataSensor
    DAG --> ResourceCheck
    DataSensor --> SparkDriver
    ResourceCheck --> SparkDriver

    SparkDriver --> Executor1 & Executor2 & Executor3 & ExecutorN

    DataLake --> Step1
    ProductMaster --> Step4
    HistoricalScores --> Step5

    Step1 --> Step2
    Step2 --> Step3
    Step3 --> Step4
    Step4 --> Step5
    Step5 --> Step6

    Step5 --> PopTable
    Step5 --> RedisGlobal
    Step6 --> CatPopTable
    Step6 --> RedisCat

    PopTable --> Validator
    RedisGlobal --> Validator
    Validator --> Notifier
    Validator --> Metrics

    style Airflow fill:#e8f5e9
    style SparkDriver fill:#fff3e0
```

---

## 5. Real-Time Hot Items Detection

```mermaid
flowchart TB
    subgraph kafka_input [Kafka Input]
        Topic["📨 user-events topic<br/>64 partitions"]
        Partition1["P0-P15"]
        Partition2["P16-P31"]
        Partition3["P32-P47"]
        Partition4["P48-P63"]
    end

    subgraph flink_cluster [Flink Cluster]
        direction TB
        JobManager["🎛️ Job Manager<br/>Coordination"]

        subgraph task_slots [Task Managers]
            TM1["TaskManager 1<br/>4 slots"]
            TM2["TaskManager 2<br/>4 slots"]
            TM3["TaskManager 3<br/>4 slots"]
            TM4["TaskManager 4<br/>4 slots"]
        end

        subgraph checkpointing [State Management]
            Checkpoint["💾 Checkpoints<br/>Every 60s"]
            StateBackend["RocksDB State<br/>Backend"]
        end
    end

    subgraph operators [Flink Operators]
        direction TB
        Source["📥 Kafka Source<br/>Watermark: 30s"]
        Filter["🔍 Event Filter<br/>view, click, cart"]
        KeyBy["🔑 Key By<br/>product_id"]

        subgraph windows [Windowing]
            Tumbling["⏱️ Tumbling Window<br/>5 minutes"]
            Sliding["⏱️ Sliding Window<br/>1h / 5min slide"]
        end

        Aggregator["➕ Weighted<br/>Aggregator"]
        HotCalc["🔥 Hot Score<br/>Calculator"]

        subgraph state [Stateful Processing]
            Baseline["📊 7-day Baseline<br/>Hourly averages"]
            Recent["📈 Recent Activity<br/>Last hour"]
        end
    end

    subgraph output [Output Sinks]
        RedisSink["🔴 Redis Sink<br/>Sorted Sets"]
        MetricsSink["📊 Prometheus<br/>Metrics"]
        AlertSink["🚨 Alert Sink<br/>score > 5.0"]
    end

    subgraph redis_output [Redis Data]
        HotGlobal[("hot_items:global")]
        HotCategory[("hot_items:category:*")]
        HotTimeline[("hot_items:timeline")]
    end

    %% Kafka to Flink
    Topic --> Partition1 & Partition2 & Partition3 & Partition4
    Partition1 --> TM1
    Partition2 --> TM2
    Partition3 --> TM3
    Partition4 --> TM4

    JobManager --> TM1 & TM2 & TM3 & TM4
    TM1 & TM2 & TM3 & TM4 --> Checkpoint
    Checkpoint --> StateBackend

    %% Operator chain
    TM1 & TM2 --> Source
    Source --> Filter
    Filter --> KeyBy
    KeyBy --> Tumbling
    KeyBy --> Sliding
    Tumbling --> Aggregator
    Sliding --> Aggregator
    Aggregator --> HotCalc
    HotCalc --> Baseline
    HotCalc --> Recent
    Baseline --> HotCalc
    Recent --> HotCalc

    %% Outputs
    HotCalc --> RedisSink
    HotCalc --> MetricsSink
    HotCalc -->|"score > 5.0"| AlertSink

    RedisSink --> HotGlobal
    RedisSink --> HotCategory
    RedisSink --> HotTimeline

    style JobManager fill:#bbdefb
    style HotCalc fill:#ffcdd2
```

---

## 6. Personalization Engine Architecture

```mermaid
flowchart TB
    subgraph input_signals [Input Signals]
        BrowseHistory["🔍 Browse History<br/>Last 50 products"]
        CartHistory["🛒 Cart History<br/>Last 30 days"]
        PurchaseHistory["💰 Purchase History"]
        Demographics["👤 Demographics<br/>Age, location"]
        SessionData["📱 Session Data<br/>Device, time"]
    end

    subgraph feature_store [Feature Store]
        direction TB

        subgraph online [Online Features - Redis]
            UserVector[("User Embedding<br/>128-dim vector")]
            RecentViews[("Recent Views<br/>Last 20 items")]
            SessionFeatures[("Session Features<br/>Current context")]
        end

        subgraph offline [Offline Features - PostgreSQL]
            CategoryAffinity[("Category Affinity<br/>Scores per category")]
            BrandAffinity[("Brand Affinity<br/>Scores per brand")]
            PricePreference[("Price Preference<br/>min/max/avg")]
            LTVScore[("Lifetime Value<br/>User segment")]
        end
    end

    subgraph personalization_engine [Personalization Engine]
        direction TB

        FeatureAssembler["🔧 Feature Assembler<br/>Build feature vector"]

        subgraph strategies [Ranking Strategies]
            Collaborative["🤝 Collaborative<br/>Similar users liked"]
            ContentBased["📝 Content-Based<br/>Similar to viewed"]
            Contextual["🌍 Contextual<br/>Time, device, location"]
        end

        MLModel["🧠 ML Model<br/>XGBoost Ranker"]

        subgraph business_rules [Business Rules]
            InventoryFilter["📦 Inventory Filter<br/>Remove OOS"]
            BoostRules["⬆️ Boost Rules<br/>Promotions, new"]
            DiversityFilter["🎨 Diversity<br/>Max per category"]
        end

        ScoreBlender["🎚️ Score Blender<br/>Weighted combination"]
    end

    subgraph output [Output]
        RankedProducts["📋 Ranked Products<br/>Top N for user"]
        ExplanationGen["💬 Explanation<br/>Why recommended"]
        Logging["📝 Feature Log<br/>For model training"]
    end

    %% Input flow
    BrowseHistory --> RecentViews
    CartHistory --> CategoryAffinity
    PurchaseHistory --> BrandAffinity
    Demographics --> LTVScore
    SessionData --> SessionFeatures

    %% Feature assembly
    UserVector --> FeatureAssembler
    RecentViews --> FeatureAssembler
    SessionFeatures --> FeatureAssembler
    CategoryAffinity --> FeatureAssembler
    BrandAffinity --> FeatureAssembler
    PricePreference --> FeatureAssembler

    %% Strategies
    FeatureAssembler --> Collaborative
    FeatureAssembler --> ContentBased
    FeatureAssembler --> Contextual
    Collaborative --> MLModel
    ContentBased --> MLModel
    Contextual --> MLModel

    %% Business rules
    MLModel --> InventoryFilter
    InventoryFilter --> BoostRules
    BoostRules --> DiversityFilter
    DiversityFilter --> ScoreBlender

    %% Output
    ScoreBlender --> RankedProducts
    ScoreBlender --> ExplanationGen
    FeatureAssembler --> Logging

    style MLModel fill:#e1bee7
    style ScoreBlender fill:#c8e6c9
```

---

## 7. Cold Start Handling Flow

```mermaid
flowchart TB
    Start([Request Received]) --> CheckUser{User Type?}

    CheckUser -->|"Anonymous"| AnonPath
    CheckUser -->|"Authenticated"| AuthPath

    subgraph AnonPath [Anonymous User Path]
        direction TB
        CheckSession{Has Session<br/>History?}
        CheckSession -->|"No"| GlobalPop["Use Global<br/>Popularity Only"]
        CheckSession -->|"Yes"| SessionBased["Session-Based<br/>Category Boost"]
        GlobalPop --> Blend1["Blend: 100% Global"]
        SessionBased --> Blend2["Blend: 80% Global<br/>+ 20% Session"]
    end

    subgraph AuthPath [Authenticated User Path]
        direction TB
        GetHistory["Fetch User<br/>History"]
        CountViews{View<br/>Count?}

        GetHistory --> CountViews

        CountViews -->|"< 10 views"| NewUser["New User<br/>Use demographics"]
        CountViews -->|"10-50 views"| LowActivity["Low Activity<br/>Light personalization"]
        CountViews -->|"50-200 views"| MedActivity["Medium Activity<br/>Balanced blend"]
        CountViews -->|"> 200 views"| HighActivity["Power User<br/>Heavy personalization"]

        NewUser --> Blend3["Blend: 70% Global<br/>+ 30% Personal"]
        LowActivity --> Blend4["Blend: 50% Global<br/>+ 50% Personal"]
        MedActivity --> Blend5["Blend: 30% Global<br/>+ 70% Personal"]
        HighActivity --> Blend6["Blend: 20% Global<br/>+ 80% Personal"]
    end

    Blend1 & Blend2 --> ApplyDiversity
    Blend3 & Blend4 & Blend5 & Blend6 --> ApplyDiversity

    ApplyDiversity["Apply Diversity<br/>Filters"] --> InjectNovelty["Inject Novelty<br/>10% new items"]
    InjectNovelty --> FinalRanking["Final Ranked<br/>Product List"]
    FinalRanking --> Response([Return Response])

    style GlobalPop fill:#ffcdd2
    style HighActivity fill:#c8e6c9
```

---

## 8. Database Schema Relationships

```mermaid
erDiagram
    PRODUCTS {
        uuid product_id PK
        string sku UK
        string name
        text description
        uuid category_id FK
        string brand
        decimal price
        jsonb image_urls
        jsonb attributes
        text[] tags
        vector embedding
        timestamp created_at
        timestamp updated_at
        boolean is_active
        string stock_status
    }

    CATEGORIES {
        uuid category_id PK
        string name
        string slug UK
        uuid parent_id FK
        int level
        ltree path
        int display_order
        boolean is_active
    }

    PRODUCT_POPULARITY {
        uuid product_id PK,FK
        float popularity_score
        int popularity_rank
        bigint view_count_7d
        bigint click_count_7d
        bigint cart_add_count_7d
        float avg_time_spent_7d
        timestamp computed_at
        float previous_score
        float score_delta
    }

    CATEGORY_POPULARITY {
        uuid category_id PK,FK
        uuid product_id PK,FK
        float popularity_score
        int category_rank
        timestamp computed_at
    }

    USER_PROFILES {
        uuid user_id PK
        string email_hash
        jsonb preferred_categories
        jsonb preferred_brands
        jsonb price_range
        vector embedding_vector
        bigint total_page_views
        bigint total_cart_adds
        bigint total_purchases
        timestamp first_seen
        timestamp last_active
    }

    USER_RECENT_ACTIVITY {
        uuid user_id PK,FK
        uuid product_id PK,FK
        string activity_type PK
        timestamp timestamp PK
        uuid session_id
    }

    USER_EVENTS {
        uuid event_id PK
        string event_type
        uuid user_id FK
        uuid session_id
        string device_id
        uuid product_id FK
        uuid category_id FK
        bigint timestamp
        jsonb metadata
    }

    CATEGORIES ||--o{ PRODUCTS : "contains"
    CATEGORIES ||--o| CATEGORIES : "parent"
    PRODUCTS ||--|| PRODUCT_POPULARITY : "has"
    CATEGORIES ||--o{ CATEGORY_POPULARITY : "has"
    PRODUCTS ||--o{ CATEGORY_POPULARITY : "ranked_in"
    USER_PROFILES ||--o{ USER_RECENT_ACTIVITY : "has"
    PRODUCTS ||--o{ USER_RECENT_ACTIVITY : "viewed"
    USER_PROFILES ||--o{ USER_EVENTS : "generates"
    PRODUCTS ||--o{ USER_EVENTS : "interacted_with"
    CATEGORIES ||--o{ USER_EVENTS : "in_category"
```

---

## 9. Infrastructure Topology

```mermaid
flowchart TB
    subgraph az1 [Availability Zone 1]
        subgraph k8s_az1 [Kubernetes Nodes]
            Node1["Worker Node 1<br/>API Pods"]
            Node2["Worker Node 2<br/>Service Pods"]
            Node3["Worker Node 3<br/>Flink Pods"]
        end

        subgraph data_az1 [Data Layer]
            PG_Primary[("PostgreSQL<br/>Primary")]
            Redis1[("Redis<br/>Primary 1")]
            Kafka1["Kafka<br/>Broker 1"]
            Kafka2["Kafka<br/>Broker 2"]
        end

        MinIO1[("MinIO<br/>Node 1")]
    end

    subgraph az2 [Availability Zone 2]
        subgraph k8s_az2 [Kubernetes Nodes]
            Node4["Worker Node 4<br/>API Pods"]
            Node5["Worker Node 5<br/>Service Pods"]
            Node6["Worker Node 6<br/>Spark Pods"]
        end

        subgraph data_az2 [Data Layer]
            PG_Replica1[("PostgreSQL<br/>Replica 1")]
            Redis2[("Redis<br/>Primary 2")]
            Kafka3["Kafka<br/>Broker 3"]
            Kafka4["Kafka<br/>Broker 4"]
        end

        MinIO2[("MinIO<br/>Node 2")]
    end

    subgraph az3 [Availability Zone 3]
        subgraph k8s_az3 [Kubernetes Nodes]
            Node7["Worker Node 7<br/>API Pods"]
            Node8["Worker Node 8<br/>Service Pods"]
        end

        subgraph data_az3 [Data Layer]
            PG_Replica2[("PostgreSQL<br/>Replica 2")]
            Redis3[("Redis<br/>Primary 3")]
            Kafka5["Kafka<br/>Broker 5"]
        end

        MinIO3[("MinIO<br/>Node 3")]
    end

    subgraph management [Management Layer]
        K8sMaster["Kubernetes<br/>Control Plane"]
        Monitoring["Monitoring<br/>Stack"]
        CI_CD["CI/CD<br/>Pipeline"]
    end

    subgraph external [External]
        GLB["Global<br/>Load Balancer"]
        CDN["CDN<br/>Edge Nodes"]
        DNS["DNS"]
    end

    %% Replication arrows
    PG_Primary -.->|"Streaming Replication"| PG_Replica1
    PG_Primary -.->|"Streaming Replication"| PG_Replica2

    Redis1 -.->|"Redis Cluster"| Redis2
    Redis2 -.->|"Redis Cluster"| Redis3
    Redis3 -.->|"Redis Cluster"| Redis1

    Kafka1 -.->|"ISR"| Kafka3
    Kafka2 -.->|"ISR"| Kafka4

    MinIO1 -.->|"Erasure Coding"| MinIO2
    MinIO2 -.->|"Erasure Coding"| MinIO3

    %% External connections
    DNS --> CDN
    CDN --> GLB
    GLB --> Node1 & Node4 & Node7

    %% Management
    K8sMaster --> Node1 & Node2 & Node3 & Node4 & Node5 & Node6 & Node7 & Node8
    Monitoring --> K8sMaster

    style PG_Primary fill:#c8e6c9
    style Redis1 fill:#ffcdd2
    style Kafka1 fill:#fff3e0
```

---

## 10. API Request-Response Flow (Detailed Sequence)

```mermaid
sequenceDiagram
    autonumber

    participant Client as 📱 Client
    participant CDN as 🌐 CDN
    participant LB as ⚖️ Load Balancer
    participant GW as 🚪 API Gateway
    participant API as 🖥️ API Server
    participant Browse as 📦 Browse Svc
    participant Rank as 📊 Ranking Svc
    participant Pers as 👤 Personalization
    participant Redis as 🔴 Redis
    participant PG as 🐘 PostgreSQL
    participant Event as 📡 Event Collector
    participant Kafka as 📨 Kafka

    Client->>CDN: GET /api/v1/browse/products?sort=personalized
    CDN->>CDN: Check cache
    CDN-->>Client: (if cached) Return cached response
    CDN->>LB: Forward request

    LB->>LB: Health check, select server
    LB->>GW: Route to gateway

    GW->>GW: Rate limit check
    GW->>GW: JWT validation
    GW->>GW: Extract user_id
    GW->>API: Forward with context

    API->>Browse: getProducts(params, user_id)

    par Parallel Cache Lookups
        Browse->>Redis: ZREVRANGE popularity:global 0 199
        Redis-->>Browse: [product_ids with scores]
    and
        Browse->>Redis: ZREVRANGE hot_items:global 0 49
        Redis-->>Browse: [hot_product_ids]
    end

    Browse->>Browse: Merge candidate set (dedupe)

    Browse->>Redis: MGET product:details:{ids}
    Redis-->>Browse: [cached products]

    opt Cache Miss
        Browse->>PG: SELECT * FROM products WHERE id IN (...)
        PG-->>Browse: [product rows]
        Browse->>Redis: MSET product:details:{ids}
    end

    Browse->>Pers: rerank(products, user_id)

    Pers->>Redis: HGETALL user:features:{user_id}
    Redis-->>Pers: user preferences

    opt Cold Start
        Pers->>PG: SELECT * FROM user_profiles WHERE user_id = ?
        PG-->>Pers: user profile
    end

    Pers->>Pers: Compute personalized scores
    Pers->>Pers: Apply category/brand boosts
    Pers-->>Browse: [reranked products]

    Browse->>Rank: applyBusinessRules(products)
    Rank->>Rank: Filter out-of-stock
    Rank->>Rank: Apply promotion boosts
    Rank->>Rank: Diversity filter
    Rank-->>Browse: [final list]

    Browse-->>API: ProductListResponse
    API-->>GW: JSON Response
    GW->>GW: Add response headers
    GW-->>LB: Response
    LB-->>CDN: Response
    CDN->>CDN: Cache response (5 min TTL)
    CDN-->>Client: 200 OK + JSON

    Note over Client,Kafka: Async Event Logging

    Client->>Event: POST /events (page_view)
    Event->>Kafka: Produce event
    Kafka-->>Event: ACK
    Event-->>Client: 202 Accepted
```

---

## 11. Failure Recovery Scenarios

```mermaid
flowchart TB
    subgraph normal [Normal Operation]
        direction LR
        N1["All systems<br/>operational"]
        N2["Full caching"]
        N3["Personalization<br/>enabled"]
    end

    subgraph redis_fail [Redis Failure]
        direction TB
        RF1{{"❌ Redis<br/>Unavailable"}}
        RF2["Fallback to<br/>PostgreSQL"]
        RF3["Increased<br/>latency"]
        RF4["Alert triggered"]
        RF1 --> RF2
        RF2 --> RF3
        RF1 --> RF4
    end

    subgraph pg_fail [PostgreSQL Failure]
        direction TB
        PF1{{"❌ Primary<br/>Down"}}
        PF2["Promote<br/>Replica"]
        PF3["Update<br/>PgBouncer"]
        PF4["Resume<br/>operations"]
        PF1 --> PF2
        PF2 --> PF3
        PF3 --> PF4
    end

    subgraph kafka_fail [Kafka Failure]
        direction TB
        KF1{{"❌ Broker<br/>Down"}}
        KF2["Partition<br/>rebalance"]
        KF3["Consumer<br/>reassignment"]
        KF4["Resume with<br/>ISR"]
        KF1 --> KF2
        KF2 --> KF3
        KF3 --> KF4
    end

    subgraph flink_fail [Flink Failure]
        direction TB
        FF1{{"❌ Job<br/>Crashed"}}
        FF2["Restore from<br/>checkpoint"]
        FF3["Replay Kafka<br/>from offset"]
        FF4["Hot items<br/>stale 5-10 min"]
        FF1 --> FF2
        FF2 --> FF3
        FF3 --> FF4
    end

    subgraph spark_fail [Spark Failure]
        direction TB
        SF1{{"❌ Job<br/>Failed"}}
        SF2["Airflow<br/>retry"]
        SF3["Manual<br/>intervention"]
        SF4["Popularity<br/>stale 24h max"]
        SF1 --> SF2
        SF2 -->|"3 retries fail"| SF3
        SF1 --> SF4
    end

    subgraph degraded [Degraded Modes]
        direction TB
        D1["Level 1: No personalization"]
        D2["Level 2: Stale popularity"]
        D3["Level 3: CDN cache only"]
        D4["Level 4: 503 Service Unavailable"]
    end

    normal --> redis_fail
    normal --> pg_fail
    normal --> kafka_fail
    normal --> flink_fail
    normal --> spark_fail

    redis_fail --> D1
    flink_fail --> D2
    pg_fail --> D3
    pg_fail --> D4

    style RF1 fill:#ffcdd2
    style PF1 fill:#ffcdd2
    style KF1 fill:#ffcdd2
    style FF1 fill:#ffcdd2
    style SF1 fill:#ffcdd2
```

---

## 12. Monitoring & Alerting Dashboard Layout

```mermaid
flowchart TB
    subgraph dashboard [Grafana Dashboard]
        direction TB

        subgraph row1 [System Health - Row 1]
            direction LR
            Panel1["🟢 API Availability<br/>99.95%"]
            Panel2["📊 Request Rate<br/>45K RPS"]
            Panel3["⏱️ p99 Latency<br/>78ms"]
            Panel4["❌ Error Rate<br/>0.02%"]
        end

        subgraph row2 [Cache Performance - Row 2]
            direction LR
            Panel5["🔴 Redis Hit Rate<br/>94.2%"]
            Panel6["💾 Memory Usage<br/>72%"]
            Panel7["🔗 Connections<br/>8,432"]
            Panel8["⚡ Ops/sec<br/>125K"]
        end

        subgraph row3 [Database - Row 3]
            direction LR
            Panel9["🐘 Query Time<br/>avg 12ms"]
            Panel10["📈 Active Connections<br/>234/500"]
            Panel11["💿 Disk Usage<br/>45%"]
            Panel12["🔄 Replication Lag<br/>0.2s"]
        end

        subgraph row4 [Streaming - Row 4]
            direction LR
            Panel13["📨 Kafka Lag<br/>1.2K msgs"]
            Panel14["🔥 Flink Throughput<br/>8.5K/s"]
            Panel15["✅ Checkpoints<br/>Success"]
            Panel16["⏳ Processing Time<br/>avg 45ms"]
        end

        subgraph row5 [Business Metrics - Row 5]
            direction LR
            Panel17["👥 Active Users<br/>125K online"]
            Panel18["🔥 Hot Items<br/>47 trending"]
            Panel19["👤 Personalized<br/>68% requests"]
            Panel20["📦 Products Viewed<br/>2.1M today"]
        end
    end

    subgraph alerts [Alert Rules]
        direction TB
        Alert1["🚨 P1: API Error > 1%"]
        Alert2["🚨 P1: Redis cluster down"]
        Alert3["⚠️ P2: Latency > 200ms"]
        Alert4["⚠️ P2: Kafka lag > 10K"]
        Alert5["📧 P3: Batch job failed"]
    end

    subgraph destinations [Alert Destinations]
        PagerDuty["📱 PagerDuty<br/>P1 alerts"]
        Slack["💬 Slack<br/>P2, P3 alerts"]
        Email["📧 Email<br/>Daily summary"]
    end

    row1 --> alerts
    row2 --> alerts
    row3 --> alerts
    row4 --> alerts

    Alert1 --> PagerDuty
    Alert2 --> PagerDuty
    Alert3 --> Slack
    Alert4 --> Slack
    Alert5 --> Email

    style Panel1 fill:#c8e6c9
    style Alert1 fill:#ffcdd2
    style Alert2 fill:#ffcdd2
```

---

## How to Export as Images

### Option 1: Mermaid Live Editor
1. Go to [mermaid.live](https://mermaid.live/)
2. Paste any diagram code
3. Click "Actions" → "Download PNG" or "Download SVG"

### Option 2: Mermaid CLI
```bash
# Install
npm install -g @mermaid-js/mermaid-cli

# Export single diagram
mmdc -i architecture-diagrams.md -o output.png -s 2

# Export with dark theme
mmdc -i architecture-diagrams.md -o output.png -t dark
```

### Option 3: VS Code
1. Install "Markdown Preview Mermaid Support" extension
2. Open this file
3. Press `Cmd+Shift+V` to preview
4. Right-click diagram → "Save as PNG"

### Option 4: Obsidian / Notion
- Both render Mermaid natively
- Copy/paste diagrams directly

