# Scaling Global Validation Queries

## The Challenge

Every custom alias creation requires a **global uniqueness check** across all regions. At scale (500M URLs/month), this becomes a bottleneck:

```mermaid
flowchart TD
    subgraph Problem["⚠️ The Problem at Scale"]
        Req["500M URLs/month<br/>~10% custom aliases<br/>= 50M global queries/month"]
        Latency["Cross-region latency:<br/>US → EU: ~80ms<br/>US → India: ~200ms"]
        Cost["DynamoDB read costs<br/>$0.25 per million reads"]
        Bottleneck["Global consistency<br/>becomes bottleneck"]
    end

    Req --> Latency --> Cost --> Bottleneck
```

---

## Solution Strategies

### Strategy 1: Bloom Filters (Recommended)

A **Bloom filter** is a probabilistic data structure that can quickly tell you:
- **"Definitely NOT exists"** → Skip DB query entirely
- **"Might exist"** → Query DB to confirm

```mermaid
flowchart TB
    subgraph BloomFilter["Bloom Filter Architecture"]
        Request["Custom alias request<br/>'my-brand'"]
        BF{"Bloom Filter<br/>Check"}
        BF -->|"Definitely NOT exists"| Create["✅ Create directly<br/>(No DB query needed)"]
        BF -->|"Might exist"| Query["Query DynamoDB"]
        Query --> Exists{"Actually exists?"}
        Exists -->|Yes| Reject["❌ 409 Conflict"]
        Exists -->|No| Create2["✅ Create<br/>(False positive)"]
    end

    subgraph Sync["Bloom Filter Sync"]
        DDB[("DynamoDB")] -->|"Stream"| Lambda["Lambda"]
        Lambda -->|"Update"| Redis[("Redis<br/>Bloom Filter")]
        Redis -->|"Replicate"| R1["US Replica"]
        Redis -->|"Replicate"| R2["EU Replica"]
        Redis -->|"Replicate"| R3["IN Replica"]
    end
```

#### Implementation

```java
@Service
public class BloomFilterAliasChecker {

    private final RedissonClient redisson;
    private final ShortUrlRepository repository;

    // Bloom filter with 0.1% false positive rate
    // Size: ~1.2GB for 1 billion entries
    private static final String BLOOM_FILTER_KEY = "url:aliases:bloom";

    public boolean mightExist(String alias) {
        RBloomFilter<String> bloomFilter = redisson.getBloomFilter(BLOOM_FILTER_KEY);
        return bloomFilter.contains(alias);
    }

    public boolean checkAndCreate(String alias, String url) {
        // Step 1: Fast Bloom filter check (local, <1ms)
        if (!mightExist(alias)) {
            // Definitely doesn't exist - create without DB query
            return createAlias(alias, url);
        }

        // Step 2: Bloom filter says "might exist" - verify with DB
        if (repository.existsByShortCode(alias)) {
            throw new AliasAlreadyExistsException(alias);
        }

        // False positive - create the alias
        return createAlias(alias, url);
    }

    private boolean createAlias(String alias, String url) {
        ShortUrl saved = repository.save(/* ... */);

        // Add to Bloom filter for future checks
        RBloomFilter<String> bloomFilter = redisson.getBloomFilter(BLOOM_FILTER_KEY);
        bloomFilter.add(alias);

        return true;
    }
}
```

#### Bloom Filter Sizing

| Entries | False Positive Rate | Memory Required |
|---------|---------------------|-----------------|
| 100M | 0.1% | ~120MB |
| 500M | 0.1% | ~600MB |
| 1B | 0.1% | ~1.2GB |
| 1B | 1% | ~800MB |

```mermaid
xychart-beta
    title "Bloom Filter: DB Queries Avoided"
    x-axis ["10M aliases", "100M aliases", "500M aliases", "1B aliases"]
    y-axis "% Queries Avoided" 0 --> 100
    bar [99.9, 99.9, 99.9, 99.9]
```

---

### Strategy 2: DynamoDB Accelerator (DAX)

**DAX** is an in-memory cache for DynamoDB that provides microsecond latency:

```mermaid
flowchart LR
    subgraph App["Application"]
        Service["UrlService"]
    end

    subgraph DAX["DAX Cluster"]
        DAX1["DAX Node 1"]
        DAX2["DAX Node 2"]
        DAX3["DAX Node 3"]
    end

    subgraph DDB["DynamoDB"]
        Table[("urls Table")]
    end

    Service -->|"Read request"| DAX1
    DAX1 -->|"Cache miss"| Table
    Table -->|"Response"| DAX1
    DAX1 -->|"Cached response<br/>(microseconds)"| Service
```

#### Configuration

```java
@Configuration
public class DaxConfig {

    @Bean
    public DynamoDbClient dynamoDbClient() {
        // Use DAX endpoint instead of direct DynamoDB
        return DynamoDbClient.builder()
            .endpointOverride(URI.create("dax://my-dax-cluster.region.amazonaws.com"))
            .build();
    }
}
```

#### DAX vs Direct DynamoDB

| Metric | Direct DynamoDB | With DAX |
|--------|-----------------|----------|
| Read Latency | 5-10ms | 0.2-0.5ms |
| Cross-region | 80-200ms | 0.5-1ms (cached) |
| Cost (reads) | $0.25/million | $0.02/million |
| Cache hit ratio | N/A | 90-99% |

---

### Strategy 3: Regional Prefix Strategy

Add an **implicit region prefix** to custom aliases to eliminate cross-region queries:

```mermaid
flowchart TB
    subgraph Strategy["Regional Prefix Strategy"]
        User["User requests: 'my-brand'"]
        Region{"Which region?"}

        Region -->|US| US_Alias["Stored as: us-my-brand"]
        Region -->|EU| EU_Alias["Stored as: eu-my-brand"]
        Region -->|IN| IN_Alias["Stored as: in-my-brand"]

        US_Alias --> US_Check["Check only US partition"]
        EU_Alias --> EU_Check["Check only EU partition"]
        IN_Alias --> IN_Check["Check only IN partition"]
    end

    subgraph Display["User-Facing URL"]
        Short["short.url/my-brand"]
        Note["Region detected from<br/>Route 53 / CloudFront"]
    end
```

#### Implementation

```java
@Service
public class RegionalAliasService {

    @Value("${AWS_REGION}")
    private String region;

    public String createAlias(String alias, String url) {
        // Add region prefix internally
        String prefixedAlias = region + "-" + alias;

        // Only check local region's partition
        if (repository.existsByShortCodeAndRegion(prefixedAlias, region)) {
            throw new AliasAlreadyExistsException(alias);
        }

        // Save with prefix
        repository.save(ShortUrl.builder()
            .shortCode(prefixedAlias)
            .displayCode(alias)  // User sees this
            .region(region)
            .build());

        return alias;
    }

    public String resolve(String alias, String requestRegion) {
        // Try current region first
        String prefixedAlias = requestRegion + "-" + alias;
        Optional<ShortUrl> url = repository.findByShortCode(prefixedAlias);

        if (url.isPresent()) {
            return url.get().getOriginalUrl();
        }

        // Fallback: check other regions (rare)
        return checkOtherRegions(alias);
    }
}
```

#### Trade-offs

| Aspect | Pros | Cons |
|--------|------|------|
| Query Speed | Local only, <5ms | N/A |
| Uniqueness | Regional, not global | Same alias in different regions |
| Complexity | Simple | Redirect routing needed |

---

### Strategy 4: Hierarchical Caching

Multi-level cache to minimize cross-region queries:

```mermaid
flowchart TB
    subgraph L1["L1: Application Cache (Caffeine)"]
        Local["In-process cache<br/>TTL: 5 minutes<br/>Size: 100K entries"]
    end

    subgraph L2["L2: Regional Cache (Redis)"]
        Redis["Regional Redis cluster<br/>TTL: 1 hour<br/>Size: 10M entries"]
    end

    subgraph L3["L3: Global Cache (DAX)"]
        DAX["DAX cluster<br/>TTL: 24 hours<br/>Near-unlimited"]
    end

    subgraph L4["L4: Source of Truth"]
        DDB[("DynamoDB<br/>Global Tables")]
    end

    Request["Check 'my-brand'"] --> L1
    L1 -->|Miss| L2
    L2 -->|Miss| L3
    L3 -->|Miss| L4
    L4 -->|Found| Populate["Populate all caches"]
```

#### Implementation

```java
@Service
public class HierarchicalAliasCache {

    private final Cache<String, Boolean> l1Cache;  // Caffeine
    private final RedisTemplate<String, Boolean> l2Cache;  // Redis
    private final DynamoDbClient l3Client;  // DAX

    public boolean exists(String alias) {
        // L1: Check in-process cache (nanoseconds)
        Boolean l1Result = l1Cache.getIfPresent(alias);
        if (l1Result != null) {
            metrics.increment("cache.l1.hit");
            return l1Result;
        }

        // L2: Check regional Redis (sub-millisecond)
        Boolean l2Result = l2Cache.opsForValue().get("alias:" + alias);
        if (l2Result != null) {
            metrics.increment("cache.l2.hit");
            l1Cache.put(alias, l2Result);
            return l2Result;
        }

        // L3: Check DAX (milliseconds)
        boolean exists = checkDax(alias);

        // Populate caches
        l1Cache.put(alias, exists);
        l2Cache.opsForValue().set("alias:" + alias, exists, Duration.ofHours(1));

        return exists;
    }
}
```

#### Cache Hit Rates at Scale

```mermaid
pie showData
    title "Cache Hit Distribution (Steady State)"
    "L1 In-Process" : 60
    "L2 Redis Regional" : 30
    "L3 DAX" : 8
    "L4 DynamoDB" : 2
```

---

### Strategy 5: Async Validation with Reservation

For extremely high throughput, use **optimistic creation** with async validation:

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Queue as SQS Queue
    participant Validator
    participant DDB as DynamoDB

    User->>API: Create "my-brand"
    API->>API: Quick local checks only
    API->>DDB: Optimistic save (pending status)
    API-->>User: 202 Accepted (pending)

    API->>Queue: Validate async

    Queue->>Validator: Process validation
    Validator->>DDB: Global uniqueness check

    alt Unique
        Validator->>DDB: Update status → active
        Validator->>User: Webhook: confirmed
    else Duplicate
        Validator->>DDB: Delete entry
        Validator->>User: Webhook: rejected
    end
```

#### Implementation

```java
@Service
public class AsyncAliasValidator {

    private final SqsTemplate sqsTemplate;

    public CreateUrlResponse createAliasAsync(CreateUrlRequest request) {
        String alias = request.customAlias();

        // Quick local validation only
        validateFormat(alias);

        // Optimistic create with PENDING status
        ShortUrl pending = repository.save(ShortUrl.builder()
            .shortCode(alias)
            .status(UrlStatus.PENDING)
            .build());

        // Queue for async validation
        sqsTemplate.send("alias-validation-queue",
            new ValidationMessage(alias, pending.getId()));

        return new CreateUrlResponse(
            pending.getId(),
            alias,
            UrlStatus.PENDING,
            "Alias is being validated. You will receive a webhook notification."
        );
    }

    @SqsListener("alias-validation-queue")
    public void validateAlias(ValidationMessage message) {
        // Full global validation
        boolean isUnique = performGlobalCheck(message.alias());

        if (isUnique) {
            repository.updateStatus(message.id(), UrlStatus.ACTIVE);
            webhookService.notify(message.userId(), "alias_confirmed", message.alias());
        } else {
            repository.delete(message.id());
            webhookService.notify(message.userId(), "alias_rejected", message.alias());
        }
    }
}
```

---

### Strategy 6: Consistent Hashing for Alias Ownership

Assign alias "ownership" to specific regions based on hash:

```mermaid
flowchart TB
    subgraph Hashing["Consistent Hash Ring"]
        Ring["Hash Ring<br/>0 → 2^32"]

        US_Range["US owns: 0 - 1.4B"]
        EU_Range["EU owns: 1.4B - 2.8B"]
        IN_Range["IN owns: 2.8B - 4.3B"]
    end

    subgraph Example["Example: 'my-brand'"]
        Hash["hash('my-brand') = 2,100,000,000"]
        Owner["Falls in EU range<br/>EU is the owner"]
        Query["Only query EU for uniqueness"]
    end

    Ring --> US_Range & EU_Range & IN_Range
    Example --> Hash --> Owner --> Query
```

#### Implementation

```java
@Service
public class ConsistentHashAliasChecker {

    private final ConsistentHash<String> hashRing;

    @PostConstruct
    public void init() {
        // Build hash ring with regions
        hashRing = new ConsistentHash<>(
            Hashing.murmur3_128(),
            100,  // Virtual nodes per region
            List.of("us-east-1", "eu-west-1", "ap-south-1")
        );
    }

    public String getOwnerRegion(String alias) {
        return hashRing.get(alias);
    }

    public boolean checkUniqueness(String alias) {
        String ownerRegion = getOwnerRegion(alias);

        if (ownerRegion.equals(currentRegion)) {
            // We own this alias - check locally
            return !repository.existsByShortCode(alias);
        } else {
            // Another region owns it - make targeted call
            return aliasClient.checkRemote(ownerRegion, alias);
        }
    }
}
```

---

## Comparison Matrix

```mermaid
quadrantChart
    title Scaling Strategies Comparison
    x-axis Low Complexity --> High Complexity
    y-axis Low Effectiveness --> High Effectiveness
    quadrant-1 Best ROI
    quadrant-2 Over-engineered
    quadrant-3 Quick Wins
    quadrant-4 Avoid

    Bloom Filter: [0.3, 0.9]
    DAX: [0.2, 0.7]
    Regional Prefix: [0.4, 0.6]
    Hierarchical Cache: [0.6, 0.85]
    Async Validation: [0.7, 0.75]
    Consistent Hashing: [0.8, 0.8]
```

| Strategy | Latency Reduction | Implementation Effort | Best For |
|----------|-------------------|----------------------|----------|
| **Bloom Filter** | 99%+ queries avoided | Medium | High read volume |
| **DAX** | 10-50x faster reads | Low | AWS-native apps |
| **Regional Prefix** | 100% local queries | Low | Regional uniqueness OK |
| **Hierarchical Cache** | 98%+ cache hits | Medium | Mixed workloads |
| **Async Validation** | Non-blocking | High | Eventual consistency OK |
| **Consistent Hashing** | Single region query | High | Predictable routing |

---

## Recommended Architecture

For a 500M URLs/month system with ~10% custom aliases:

```mermaid
flowchart TB
    subgraph Request["Incoming Request"]
        Alias["Custom alias: 'my-brand'"]
    end

    subgraph L1["Layer 1: Bloom Filter"]
        BF{"Bloom Filter<br/>(Redis)"}
        BF -->|"NOT exists"| FastPath["✅ Fast path<br/>Create directly"]
        BF -->|"MIGHT exist"| L2
    end

    subgraph L2["Layer 2: Local Cache"]
        LC{"Caffeine Cache<br/>(In-process)"}
        LC -->|"Cached"| Return["Return cached result"]
        LC -->|"Miss"| L3
    end

    subgraph L3["Layer 3: Regional Cache"]
        RC{"Redis Cluster<br/>(Regional)"}
        RC -->|"Cached"| Return2["Return + populate L1"]
        RC -->|"Miss"| L4
    end

    subgraph L4["Layer 4: DAX"]
        DAX{"DynamoDB DAX"}
        DAX -->|"Hit"| Return3["Return + populate L2,L3"]
        DAX -->|"Miss"| DDB
    end

    subgraph DDB["DynamoDB Global Tables"]
        Table[("Source of Truth")]
    end

    Alias --> BF
```

### Expected Performance

| Metric | Without Optimization | With Full Stack |
|--------|---------------------|-----------------|
| Avg Latency | 80-200ms | 0.5-2ms |
| P99 Latency | 500ms | 10ms |
| DB Queries | 50M/month | 500K/month (99% reduction) |
| Cost | $12,500/month | $125/month |

---

## Implementation Priority

```mermaid
gantt
    title Implementation Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1
    DAX Setup           :p1, 2024-01-01, 1w
    Basic Caching       :p2, after p1, 1w
    section Phase 2
    Bloom Filter        :p3, after p2, 2w
    Redis Cluster       :p4, after p3, 1w
    section Phase 3
    Hierarchical Cache  :p5, after p4, 2w
    Monitoring          :p6, after p5, 1w
    section Phase 4 (If needed)
    Consistent Hashing  :p7, after p6, 3w
    Async Validation    :p8, after p7, 2w
```

1. **Phase 1 (Week 1-2)**: DAX + Basic caching - 80% improvement
2. **Phase 2 (Week 3-5)**: Bloom Filter + Redis - 95% improvement
3. **Phase 3 (Week 6-8)**: Hierarchical cache - 99% improvement
4. **Phase 4 (If needed)**: Advanced strategies for extreme scale
