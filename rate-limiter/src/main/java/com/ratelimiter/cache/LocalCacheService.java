package com.ratelimiter.cache;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.ratelimiter.config.RateLimiterProperties;
import com.ratelimiter.domain.RateLimitKey;
import com.ratelimiter.domain.RateLimitRule;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.BiConsumer;

/**
 * Local cache service using Caffeine for high-performance rate limiting.
 *
 * <p>This service provides a local cache layer that reduces Redis round-trips
 * by caching counters locally and batching updates to Redis. This is critical
 * for achieving 100K+ RPS throughput.
 *
 * <p>Strategy:
 * <ul>
 *   <li>Local Caffeine cache holds recent counters (TTL: window size)</li>
 *   <li>Increment locally, batch sync to Redis periodically</li>
 *   <li>Accept slight over-counting (best-effort consistency)</li>
 * </ul>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LocalCacheService {

    private final RateLimiterProperties properties;

    // Cache for counter values: key -> count
    private Cache<String, AtomicLong> counterCache;

    // Buffer for pending increments to sync to Redis: key -> pending increment
    private final ConcurrentHashMap<String, AtomicLong> syncBuffer = new ConcurrentHashMap<>();

    // Callback for syncing to Redis
    private BiConsumer<String, Long> syncCallback;

    @PostConstruct
    public void init() {
        var cacheConfig = properties.getLocalCache();

        this.counterCache = Caffeine.newBuilder()
            .maximumSize(cacheConfig.getMaxEntries())
            .expireAfterWrite(Duration.ofSeconds(cacheConfig.getTtlSeconds()))
            .recordStats()
            .build();

        log.info("Initialized local cache with maxEntries={}, ttlSeconds={}",
            cacheConfig.getMaxEntries(), cacheConfig.getTtlSeconds());
    }

    /**
     * Sets the callback for syncing increments to Redis.
     */
    public void setSyncCallback(BiConsumer<String, Long> callback) {
        this.syncCallback = callback;
    }

    /**
     * Gets the current count from local cache.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param windowStart the window start timestamp
     * @return the cached count, or null if not cached
     */
    public Long getCount(RateLimitKey key, RateLimitRule rule, long windowStart) {
        if (!properties.getLocalCache().isEnabled()) {
            return null;
        }

        String cacheKey = buildCacheKey(key, rule, windowStart);
        AtomicLong counter = counterCache.getIfPresent(cacheKey);
        return counter != null ? counter.get() : null;
    }

    /**
     * Gets or creates a counter in the local cache.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param windowStart the window start timestamp
     * @param initialValue the initial value if creating new counter
     * @return the counter value
     */
    public long getOrCreate(RateLimitKey key, RateLimitRule rule, long windowStart, long initialValue) {
        if (!properties.getLocalCache().isEnabled()) {
            return initialValue;
        }

        String cacheKey = buildCacheKey(key, rule, windowStart);
        AtomicLong counter = counterCache.get(cacheKey, k -> new AtomicLong(initialValue));
        return counter.get();
    }

    /**
     * Increments the counter locally and buffers the increment for sync.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param windowStart the window start timestamp
     * @param amount the amount to increment
     * @return the new count after increment
     */
    public long incrementLocal(RateLimitKey key, RateLimitRule rule, long windowStart, int amount) {
        if (!properties.getLocalCache().isEnabled()) {
            return amount;
        }

        String cacheKey = buildCacheKey(key, rule, windowStart);

        // Increment local counter
        AtomicLong counter = counterCache.get(cacheKey, k -> new AtomicLong(0));
        long newValue = counter.addAndGet(amount);

        // Buffer the increment for sync
        syncBuffer.computeIfAbsent(cacheKey, k -> new AtomicLong(0)).addAndGet(amount);

        return newValue;
    }

    /**
     * Updates the local cache with a value from Redis.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param windowStart the window start timestamp
     * @param value the value from Redis
     */
    public void updateFromRedis(RateLimitKey key, RateLimitRule rule, long windowStart, long value) {
        if (!properties.getLocalCache().isEnabled()) {
            return;
        }

        String cacheKey = buildCacheKey(key, rule, windowStart);

        // Get any pending local increments
        AtomicLong pendingIncrement = syncBuffer.get(cacheKey);
        long pending = pendingIncrement != null ? pendingIncrement.get() : 0;

        // Update cache with Redis value + pending local increments
        counterCache.put(cacheKey, new AtomicLong(value + pending));
    }

    /**
     * Scheduled task to sync buffered increments to Redis.
     */
    @Scheduled(fixedRateString = "${rate-limiter.local-cache.sync-interval-ms:100}")
    public void syncToRedis() {
        if (!properties.getLocalCache().isEnabled() || syncCallback == null) {
            return;
        }

        if (syncBuffer.isEmpty()) {
            return;
        }

        // Drain and sync buffer
        for (Map.Entry<String, AtomicLong> entry : syncBuffer.entrySet()) {
            String key = entry.getKey();
            long increment = entry.getValue().getAndSet(0);

            if (increment > 0) {
                try {
                    syncCallback.accept(key, increment);
                } catch (Exception e) {
                    // Put the increment back in the buffer on failure
                    syncBuffer.computeIfAbsent(key, k -> new AtomicLong(0)).addAndGet(increment);
                    log.warn("Failed to sync increment for key {}: {}", key, e.getMessage());
                }
            }

            // Remove entries with 0 increment
            syncBuffer.computeIfPresent(key, (k, v) -> v.get() == 0 ? null : v);
        }
    }

    /**
     * Gets cache statistics.
     */
    public CacheStats getStats() {
        var stats = counterCache.stats();
        return new CacheStats(
            stats.hitCount(),
            stats.missCount(),
            stats.hitRate(),
            counterCache.estimatedSize(),
            syncBuffer.size()
        );
    }

    /**
     * Clears the local cache and sync buffer.
     */
    public void clear() {
        counterCache.invalidateAll();
        syncBuffer.clear();
    }

    private String buildCacheKey(RateLimitKey key, RateLimitRule rule, long windowStart) {
        return key.toRedisKey(properties.getRedis().getKeyPrefix(), windowStart);
    }

    /**
     * Cache statistics record.
     */
    public record CacheStats(
        long hitCount,
        long missCount,
        double hitRate,
        long estimatedSize,
        long pendingSyncCount
    ) {}
}
