# TTL Expiry and Slug Reuse Across Regions

## The Challenge

When a URL expires (TTL expiry), its slug becomes available for reuse. This creates cache invalidation challenges across our scaling strategies:

```mermaid
flowchart TD
    subgraph Problem["⚠️ The Problem"]
        T1["T=0: User creates 'promo2024'"]
        T2["T=30 days: URL expires (TTL)"]
        T3["T=31 days: New user wants 'promo2024'"]
        
        Issue["Caches still think 'promo2024' exists!<br/>New creation blocked incorrectly"]
    end

    T1 --> T2 --> T3 --> Issue

    subgraph Cache["Stale Cache State"]
        BF["Bloom Filter: contains('promo2024') = true"]
        L1["L1 Cache: 'promo2024' → EXISTS"]
        Redis["Redis: 'promo2024' → old_url"]
    end

    Issue --> Cache
```

---

## Strategy Analysis

### Strategy 1: Bloom Filter

#### The Problem

**Bloom filters do NOT support deletion.** Once an alias is added, it stays forever.

```mermaid
flowchart TD
    subgraph BloomProblem["❌ Bloom Filter Limitation"]
        Add["Add 'promo2024' to Bloom Filter"]
        Expire["URL expires after 30 days"]
        Check["Check 'promo2024'"]
        Result["Still returns: MIGHT EXIST<br/>(False positive forever!)"]
    end

    Add --> Expire --> Check --> Result

    subgraph Impact["Impact"]
        I1["Cannot reuse expired slugs"]
        I2["Bloom filter fills up over time"]
        I3["False positive rate increases"]
    end

    Result --> Impact
```

#### Solutions

##### Solution A: Counting Bloom Filter

```mermaid
flowchart LR
    subgraph CBF["Counting Bloom Filter"]
        Add["add('promo2024')<br/>Increment counters"]
        Remove["remove('promo2024')<br/>Decrement counters"]
        Check["check('promo2024')<br/>All counters > 0?"]
    end

    Add --> Remove --> Check
```

```java
@Component
public class CountingBloomFilterService {
    
    // Counting Bloom Filter using Redis
    private static final String CBF_PREFIX = "cbf:alias:";
    
    public void add(String alias) {
        byte[] hash = hashAlias(alias);
        for (int i = 0; i < NUM_HASH_FUNCTIONS; i++) {
            int position = getPosition(hash, i);
            redisTemplate.opsForValue().increment(CBF_PREFIX + position);
        }
    }
    
    public void remove(String alias) {
        byte[] hash = hashAlias(alias);
        for (int i = 0; i < NUM_HASH_FUNCTIONS; i++) {
            int position = getPosition(hash, i);
            redisTemplate.opsForValue().decrement(CBF_PREFIX + position);
        }
    }
    
    public boolean mightExist(String alias) {
        byte[] hash = hashAlias(alias);
        for (int i = 0; i < NUM_HASH_FUNCTIONS; i++) {
            int position = getPosition(hash, i);
            Long count = redisTemplate.opsForValue().get(CBF_PREFIX + position);
            if (count == null || count <= 0) {
                return false; // Definitely doesn't exist
            }
        }
        return true; // Might exist
    }
}
```

##### Solution B: Rotating Bloom Filters

```mermaid
flowchart TB
    subgraph Rotating["Rotating Bloom Filters"]
        Current["Current Filter<br/>(Active writes)"]
        Previous["Previous Filter<br/>(Read-only)"]
        Archive["Archived Filter<br/>(Discarded)"]
    end

    subgraph Timeline["Rotation Schedule"]
        W1["Week 1-2: Filter A active"]
        W2["Week 3-4: Filter B active, A read-only"]
        W3["Week 5-6: Filter C active, B read-only, A discarded"]
    end

    subgraph Check["Existence Check"]
        C1["Check Current Filter"]
        C2["Check Previous Filter"]
        C3["Return: exists in either?"]
    end

    W1 --> W2 --> W3
    Current --> C1
    Previous --> C2
    C1 --> C3
    C2 --> C3
```

```java
@Component
public class RotatingBloomFilter {
    
    private final Duration rotationPeriod = Duration.ofDays(14);
    private RBloomFilter<String> currentFilter;
    private RBloomFilter<String> previousFilter;
    
    @Scheduled(fixedRate = 14, timeUnit = TimeUnit.DAYS)
    public void rotate() {
        // Discard old previous, current becomes previous
        redisson.getBloomFilter("bloom:archive").delete();
        previousFilter.rename("bloom:archive");
        currentFilter.rename("bloom:previous");
        
        // Create new current
        currentFilter = redisson.getBloomFilter("bloom:current");
        currentFilter.tryInit(expectedInsertions, falsePositiveRate);
        
        log.info("Rotated Bloom filters");
    }
    
    public boolean mightExist(String alias) {
        return currentFilter.contains(alias) || 
               previousFilter.contains(alias);
    }
    
    public void add(String alias) {
        currentFilter.add(alias);
    }
}
```

##### Solution C: Time-Partitioned Bloom Filters

```mermaid
flowchart LR
    subgraph Partitioned["Time-Partitioned Filters"]
        BF_Jan["January Filter"]
        BF_Feb["February Filter"]
        BF_Mar["March Filter"]
    end

    subgraph Query["Query All Active"]
        Q["Check alias"]
        Q --> BF_Jan
        Q --> BF_Feb
        Q --> BF_Mar
    end

    subgraph Expiry["Auto-Expire"]
        E["Delete filters older<br/>than max TTL (e.g., 1 year)"]
    end
```

#### Bloom Filter Summary

| Solution | Pros | Cons | Recommended |
|----------|------|------|-------------|
| Counting Bloom | Supports deletion | 4x memory, counter overflow risk | ⚠️ Medium scale |
| Rotating Bloom | Simple, auto-cleanup | Brief false negatives during rotation | ✅ Large scale |
| Time-Partitioned | Precise TTL alignment | Complex query across partitions | ✅ Variable TTLs |

---

### Strategy 2: DynamoDB Accelerator (DAX)

#### How It Works with TTL

DAX automatically handles TTL because DynamoDB TTL deletes the source record:

```mermaid
sequenceDiagram
    participant App
    participant DAX
    participant DDB as DynamoDB

    Note over DDB: URL expires (TTL)
    DDB->>DDB: Background delete 'promo2024'
    
    Note over App: New user requests 'promo2024'
    App->>DAX: exists('promo2024')?
    
    alt DAX cache still has stale entry
        DAX-->>App: true (stale!)
        Note over App: Incorrectly blocked
    else DAX cache expired (TTL alignment)
        DAX->>DDB: Query
        DDB-->>DAX: Not found
        DAX-->>App: false ✓
        Note over App: Can create!
    end
```

#### The Problem: TTL Misalignment

```mermaid
flowchart TD
    subgraph Misalignment["TTL Misalignment Window"]
        DDB_TTL["DynamoDB TTL: 30 days"]
        DAX_TTL["DAX Cache TTL: 24 hours"]
        Gap["Gap: Up to 24 hours where<br/>DAX thinks expired item exists"]
    end

    subgraph Impact["Impact"]
        Block["New creation blocked<br/>for up to 24 hours"]
    end

    DDB_TTL --> Gap
    DAX_TTL --> Gap
    Gap --> Impact
```

#### Solution: TTL-Aware DAX Configuration

```java
@Configuration
public class DaxTtlConfig {
    
    // Set DAX TTL shorter than minimum URL TTL
    // If min URL TTL = 1 day, set DAX TTL = 1 hour
    @Bean
    public DaxClientConfig daxConfig() {
        return DaxClientConfig.builder()
            .itemTtl(Duration.ofHours(1))  // Short TTL
            .queryTtl(Duration.ofMinutes(5))
            .build();
    }
}

@Service
public class TtlAwareAliasChecker {
    
    public boolean exists(String alias) {
        // First check DAX
        Optional<ShortUrl> cached = daxRepository.findByShortCode(alias);
        
        if (cached.isEmpty()) {
            return false;
        }
        
        // Verify not expired (DAX might have stale data)
        ShortUrl url = cached.get();
        if (url.getExpiresAt() != null && 
            url.getExpiresAt().isBefore(Instant.now())) {
            // Expired! Invalidate DAX cache
            daxRepository.evict(alias);
            return false;
        }
        
        return true;
    }
}
```

#### DAX Summary

| Aspect | Status | Mitigation |
|--------|--------|------------|
| Auto-cleanup | ✅ Works (DynamoDB TTL) | N/A |
| Cache staleness | ⚠️ Up to DAX TTL | Reduce DAX TTL |
| Cross-region | ✅ Each region has own DAX | N/A |

---

### Strategy 3: Regional Prefix Strategy

#### How TTL Works

Each region handles its own TTL independently - **no cross-region coordination needed**:

```mermaid
flowchart TB
    subgraph US["🇺🇸 US-EAST-1"]
        US_Create["Create: us-promo2024"]
        US_Expire["Expires after 30 days"]
        US_Reuse["Reuse: us-promo2024 available"]
    end

    subgraph EU["🇪🇺 EU-WEST-1"]
        EU_Create["Create: eu-promo2024"]
        EU_Expire["Expires after 30 days"]
        EU_Reuse["Reuse: eu-promo2024 available"]
    end

    US_Create --> US_Expire --> US_Reuse
    EU_Create --> EU_Expire --> EU_Reuse

    Note["✅ No cross-region invalidation needed!"]
```

#### Why It Works

```mermaid
flowchart LR
    subgraph Independence["Regional Independence"]
        A["Each region manages own aliases"]
        B["TTL handled locally"]
        C["Cache invalidation is local"]
        D["No global coordination"]
    end

    A --> B --> C --> D
```

#### Regional Prefix Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| TTL Handling | ✅ Perfect | Local only |
| Cache Invalidation | ✅ Simple | Local caches only |
| Slug Reuse | ✅ Immediate | No cross-region wait |
| Trade-off | ⚠️ | Same alias possible in different regions |

---

### Strategy 4: Hierarchical Caching

#### The Problem: Multi-Layer Staleness

```mermaid
flowchart TD
    subgraph Stale["Stale Data in Multiple Layers"]
        L1["L1 (Caffeine): TTL 5 min<br/>Still has 'promo2024'"]
        L2["L2 (Redis): TTL 1 hour<br/>Still has 'promo2024'"]
        L3["L3 (DAX): TTL 24 hours<br/>Still has 'promo2024'"]
        L4["L4 (DynamoDB): DELETED<br/>'promo2024' expired"]
    end

    L1 --> L2 --> L3 --> L4

    subgraph Problem["Problem"]
        P["Query stops at L1, L2, or L3<br/>Never sees L4 deletion"]
    end
```

#### Solution: TTL Alignment + Active Invalidation

```mermaid
flowchart TB
    subgraph TTLAlignment["TTL Alignment Strategy"]
        Rule["Cache TTL < Source TTL"]
        
        L1_TTL["L1: 5 minutes"]
        L2_TTL["L2: 30 minutes"]
        L3_TTL["L3: 2 hours"]
        URL_TTL["Min URL TTL: 24 hours"]
    end

    subgraph ActiveInvalidation["Active Invalidation via DynamoDB Streams"]
        Stream["DynamoDB Stream"]
        Lambda["Lambda Function"]
        Invalidate["Invalidate all cache layers"]
    end

    Rule --> L1_TTL --> L2_TTL --> L3_TTL --> URL_TTL
    Stream --> Lambda --> Invalidate
```

```java
// Lambda function triggered by DynamoDB Streams
public class CacheInvalidationHandler implements RequestHandler<DynamodbEvent, Void> {
    
    private final RedisTemplate<String, Object> redis;
    private final SnsClient sns;
    
    @Override
    public Void handleRequest(DynamodbEvent event, Context context) {
        for (DynamodbStreamRecord record : event.getRecords()) {
            if ("REMOVE".equals(record.getEventName())) {
                // URL was deleted (TTL or manual)
                String alias = record.getDynamodb().getKeys()
                    .get("short_code").getS();
                
                invalidateAllCaches(alias);
            }
        }
        return null;
    }
    
    private void invalidateAllCaches(String alias) {
        // L2: Redis (direct)
        redis.delete("alias:" + alias);
        
        // L1: Caffeine (via SNS to all instances)
        sns.publish(PublishRequest.builder()
            .topicArn(CACHE_INVALIDATION_TOPIC)
            .message(alias)
            .build());
        
        // L3: DAX (via DynamoDB - automatic)
        // DAX watches DynamoDB streams internally
        
        log.info("Invalidated caches for expired alias: {}", alias);
    }
}
```

```java
// Application-side SNS listener for L1 invalidation
@Component
public class L1CacheInvalidationListener {
    
    private final Cache<String, Boolean> l1Cache;
    
    @SqsListener("cache-invalidation-queue")
    public void onInvalidation(String alias) {
        l1Cache.invalidate(alias);
        log.debug("Invalidated L1 cache for: {}", alias);
    }
}
```

#### Hierarchical Cache Invalidation Flow

```mermaid
sequenceDiagram
    participant DDB as DynamoDB
    participant Stream as DDB Streams
    participant Lambda
    participant SNS
    participant Redis as L2 Redis
    participant App as App Instances
    participant L1 as L1 Caffeine

    Note over DDB: TTL expires, record deleted
    DDB->>Stream: REMOVE event
    Stream->>Lambda: Trigger
    
    par Invalidate L2
        Lambda->>Redis: DELETE alias:promo2024
    and Invalidate L1 (all instances)
        Lambda->>SNS: Publish invalidation
        SNS->>App: Fan out to all instances
        App->>L1: invalidate('promo2024')
    end

    Note over DDB,L1: All caches invalidated within seconds
```

#### Hierarchical Cache Summary

| Layer | TTL | Invalidation Method |
|-------|-----|---------------------|
| L1 Caffeine | 5 min | SNS → SQS fan-out |
| L2 Redis | 30 min | Lambda direct delete |
| L3 DAX | 2 hours | DynamoDB Streams (automatic) |
| L4 DynamoDB | Source | TTL auto-delete |

---

### Strategy 5: Async Validation

#### How TTL Works

Async validation **always checks the source** eventually, so TTL works naturally:

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Queue as SQS
    participant Validator
    participant DDB as DynamoDB

    Note over DDB: 'promo2024' expired yesterday

    User->>API: Create 'promo2024'
    API->>API: Quick checks (format, etc.)
    API->>DDB: Optimistic save (PENDING)
    API-->>User: 202 Accepted

    API->>Queue: Validate async

    Queue->>Validator: Process
    Validator->>DDB: Check 'promo2024' status
    
    Note over DDB: Old record deleted by TTL<br/>New PENDING record exists
    DDB-->>Validator: Only PENDING exists
    
    Validator->>DDB: Update status → ACTIVE
    Validator-->>User: Webhook: confirmed ✓
```

#### Edge Case: Race with TTL

```mermaid
sequenceDiagram
    participant User1 as User 1 (Original)
    participant User2 as User 2 (New)
    participant DDB as DynamoDB

    Note over DDB: 'promo2024' about to expire

    User2->>DDB: Create 'promo2024' (PENDING)
    Note over DDB: TTL triggers, deletes old record
    Note over DDB: New PENDING record remains
    
    DDB-->>User2: Validated → ACTIVE ✓
```

#### Async Validation Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| TTL Handling | ✅ Perfect | Always checks source |
| Race Conditions | ✅ Safe | Conditional writes |
| User Experience | ⚠️ | Eventual confirmation |

---

### Strategy 6: Consistent Hashing

#### How TTL Works

The owning region handles TTL and must broadcast invalidation:

```mermaid
flowchart TB
    subgraph Owner["Owner Region (EU)"]
        Create["'promo2024' created in EU"]
        TTL["TTL expires"]
        Delete["Record deleted"]
        Broadcast["Broadcast invalidation"]
    end

    subgraph Other["Other Regions"]
        US_Cache["US: Invalidate cache"]
        IN_Cache["IN: Invalidate cache"]
    end

    Create --> TTL --> Delete --> Broadcast
    Broadcast --> US_Cache
    Broadcast --> IN_Cache
```

#### Implementation

```java
@Component
public class ConsistentHashTtlHandler {
    
    private final ConsistentHash<String> hashRing;
    private final SnsClient sns;
    
    // Called when DynamoDB TTL deletes a record
    @DynamoDbStreamListener
    public void onTtlExpiry(DynamodbStreamRecord record) {
        if (!"REMOVE".equals(record.getEventName())) return;
        
        String alias = record.getDynamodb().getKeys()
            .get("short_code").getS();
        String ownerRegion = hashRing.get(alias);
        
        if (currentRegion.equals(ownerRegion)) {
            // We are the owner - broadcast to other regions
            broadcastInvalidation(alias);
        }
    }
    
    private void broadcastInvalidation(String alias) {
        // SNS topic with cross-region subscriptions
        sns.publish(PublishRequest.builder()
            .topicArn(CROSS_REGION_INVALIDATION_TOPIC)
            .message(new InvalidationMessage(alias, Instant.now()).toJson())
            .build());
    }
    
    @SnsListener("invalidation-queue")
    public void onInvalidationReceived(InvalidationMessage msg) {
        // Invalidate local caches
        localCache.invalidate(msg.alias());
        redisCache.delete(msg.alias());
    }
}
```

#### Cross-Region Invalidation Flow

```mermaid
sequenceDiagram
    participant EU_DDB as EU DynamoDB
    participant EU_App as EU App
    participant SNS as SNS (Global)
    participant US_App as US App
    participant IN_App as IN App

    Note over EU_DDB: TTL expires 'promo2024'
    EU_DDB->>EU_App: Stream: REMOVE
    
    EU_App->>EU_App: I own 'promo2024' (hash)
    EU_App->>SNS: Broadcast invalidation
    
    par Fan out
        SNS->>US_App: Invalidate 'promo2024'
        US_App->>US_App: Clear local caches
    and
        SNS->>IN_App: Invalidate 'promo2024'
        IN_App->>IN_App: Clear local caches
    end

    Note over EU_App,IN_App: All regions ready for reuse
```

#### Consistent Hashing Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| TTL Handling | ✅ Works | Owner broadcasts |
| Cross-region sync | ⚠️ Latency | SNS propagation delay |
| Failure mode | ⚠️ | If owner down, invalidation delayed |

---

## Comparison Matrix: TTL Handling

```mermaid
flowchart TB
    subgraph Comparison["Strategy Comparison for TTL/Reuse"]
        BF["Bloom Filter<br/>❌ Doesn't support deletion<br/>✅ With Counting/Rotating"]
        DAX["DAX<br/>⚠️ Cache staleness window<br/>✅ With TTL alignment"]
        Regional["Regional Prefix<br/>✅ Perfect - local only"]
        Hierarchical["Hierarchical Cache<br/>⚠️ Multi-layer staleness<br/>✅ With active invalidation"]
        Async["Async Validation<br/>✅ Perfect - always checks source"]
        Hash["Consistent Hashing<br/>⚠️ Cross-region broadcast delay<br/>✅ With SNS"]
    end
```

| Strategy | TTL Support | Slug Reuse | Complexity | Recommendation |
|----------|-------------|------------|------------|----------------|
| **Bloom Filter** | ❌ Native | ❌ Blocked forever | High (need variants) | Use Counting/Rotating |
| **DAX** | ✅ Auto | ⚠️ Delayed (cache TTL) | Low | Align cache TTL |
| **Regional Prefix** | ✅ Perfect | ✅ Immediate | Low | Best for TTL |
| **Hierarchical Cache** | ⚠️ Complex | ⚠️ Delayed | High | Need active invalidation |
| **Async Validation** | ✅ Perfect | ✅ Immediate | Medium | Great for TTL |
| **Consistent Hashing** | ✅ Works | ⚠️ Propagation delay | High | Good with SNS |

---

## Recommended Architecture for TTL Support

```mermaid
flowchart TB
    subgraph Recommended["Recommended: Hybrid Approach"]
        subgraph Layer1["Fast Path: Counting Bloom Filter"]
            CBF["Counting Bloom Filter<br/>Supports add AND remove"]
        end

        subgraph Layer2["Validation: DAX with Short TTL"]
            DAX["DAX (1 hour TTL)<br/>Auto-invalidates"]
        end

        subgraph Layer3["Invalidation: DynamoDB Streams"]
            Streams["DynamoDB Streams"]
            Lambda["Lambda Invalidator"]
            SNS["SNS Fan-out"]
        end
    end

    CBF --> DAX
    Streams --> Lambda --> SNS
    SNS -->|"Decrement"| CBF
    SNS -->|"Invalidate"| DAX
```

### Implementation

```java
@Service
public class TtlAwareAliasService {
    
    private final CountingBloomFilter bloomFilter;
    private final DaxRepository daxRepository;
    private final ShortUrlRepository repository;
    
    public boolean canCreate(String alias) {
        // Step 1: Counting Bloom Filter (sub-ms)
        if (!bloomFilter.mightExist(alias)) {
            return true; // Definitely available
        }
        
        // Step 2: DAX check (ms)
        Optional<ShortUrl> cached = daxRepository.findByShortCode(alias);
        if (cached.isEmpty()) {
            // Bloom filter false positive
            return true;
        }
        
        // Step 3: Check if expired
        ShortUrl url = cached.get();
        if (isExpired(url)) {
            // Expired but not yet cleaned up
            // Trigger async cleanup and allow reuse
            triggerCleanup(alias);
            return true;
        }
        
        return false; // Alias in use
    }
    
    // Called by DynamoDB Streams Lambda
    @SnsListener("alias-ttl-expired")
    public void onAliasExpired(String alias) {
        // Remove from Counting Bloom Filter
        bloomFilter.remove(alias);
        
        // DAX auto-invalidates via DynamoDB Streams
        log.info("Alias {} expired and removed from bloom filter", alias);
    }
    
    public void createAlias(String alias, String url) {
        if (!canCreate(alias)) {
            throw new AliasAlreadyExistsException(alias);
        }
        
        repository.save(/* ... */);
        
        // Add to Counting Bloom Filter
        bloomFilter.add(alias);
    }
}
```

---

## Summary

```mermaid
mindmap
  root((TTL & Slug Reuse))
    Bloom Filter
      Problem: No deletion
      Solution: Counting Bloom
      Solution: Rotating filters
    DAX
      Problem: Cache staleness
      Solution: Short TTL
      Solution: Expiry check
    Regional Prefix
      Works perfectly
      No cross-region sync
    Hierarchical Cache
      Problem: Multi-layer stale
      Solution: Active invalidation
      Solution: DDB Streams + SNS
    Async Validation
      Works perfectly
      Always checks source
    Consistent Hashing
      Problem: Broadcast delay
      Solution: SNS fan-out
```

### Key Takeaways

1. **Bloom Filters need special handling** - Use Counting or Rotating variants
2. **DAX works but needs TTL alignment** - Set DAX TTL < min URL TTL
3. **Regional Prefix is best for TTL** - No cross-region coordination
4. **Hierarchical Cache needs active invalidation** - DynamoDB Streams + Lambda + SNS
5. **Async Validation handles TTL naturally** - Always eventual consistency
6. **Consistent Hashing needs broadcast** - Owner notifies other regions
