package com.urlshortener.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

/**
 * Cache service supporting both Redis and in-memory caching
 */
@Slf4j
@Service
public class CacheService {

    private static final String URL_PREFIX = "urlsh:url:";
    private static final String RATE_PREFIX = "urlsh:rate:";

    private final StringRedisTemplate redisTemplate;
    private final Map<String, CacheEntry> memoryCache;
    private final boolean useRedis;

    @Value("${url-shortener.cache.ttl-seconds:86400}")
    private long defaultTtlSeconds;

    public CacheService(
            Optional<StringRedisTemplate> redisTemplate,
            @Value("${url-shortener.cache.type:memory}") String cacheType) {

        this.useRedis = "redis".equalsIgnoreCase(cacheType) && redisTemplate.isPresent();
        this.redisTemplate = redisTemplate.orElse(null);
        this.memoryCache = useRedis ? null : new ConcurrentHashMap<>();

        log.info("Cache service initialized with type: {}", useRedis ? "redis" : "memory");
    }

    /**
     * Get URL from cache
     */
    public Optional<String> getUrl(String code) {
        String key = URL_PREFIX + code;

        if (useRedis) {
            try {
                String value = redisTemplate.opsForValue().get(key);
                return Optional.ofNullable(value);
            } catch (Exception e) {
                log.warn("Redis get failed for key {}: {}", key, e.getMessage());
                return Optional.empty();
            }
        } else {
            return getFromMemory(key);
        }
    }

    /**
     * Set URL in cache with TTL
     */
    public void setUrl(String code, String url, long ttlSeconds) {
        String key = URL_PREFIX + code;

        if (useRedis) {
            try {
                redisTemplate.opsForValue().set(key, url, Duration.ofSeconds(ttlSeconds));
            } catch (Exception e) {
                log.warn("Redis set failed for key {}: {}", key, e.getMessage());
            }
        } else {
            setInMemory(key, url, ttlSeconds);
        }
    }

    /**
     * Set URL in cache with default TTL
     */
    public void setUrl(String code, String url) {
        setUrl(code, url, defaultTtlSeconds);
    }

    /**
     * Delete URL from cache
     */
    public void deleteUrl(String code) {
        String key = URL_PREFIX + code;

        if (useRedis) {
            try {
                redisTemplate.delete(key);
            } catch (Exception e) {
                log.warn("Redis delete failed for key {}: {}", key, e.getMessage());
            }
        } else if (memoryCache != null) {
            memoryCache.remove(key);
        }
    }

    /**
     * Increment rate limit counter
     * @return Current count after increment
     */
    public long incrementRateLimit(String identifier, long windowSeconds) {
        String key = RATE_PREFIX + identifier;

        if (useRedis) {
            try {
                Long count = redisTemplate.opsForValue().increment(key);
                // Set expiry only on first increment
                if (count != null && count == 1) {
                    redisTemplate.expire(key, windowSeconds, TimeUnit.SECONDS);
                }
                return count != null ? count : 0;
            } catch (Exception e) {
                log.warn("Redis increment failed for key {}: {}", key, e.getMessage());
                return 0;
            }
        } else {
            return incrementInMemory(key, windowSeconds);
        }
    }

    /**
     * Get current rate limit count
     */
    public long getRateLimitCount(String identifier) {
        String key = RATE_PREFIX + identifier;

        if (useRedis) {
            try {
                String value = redisTemplate.opsForValue().get(key);
                return value != null ? Long.parseLong(value) : 0;
            } catch (Exception e) {
                return 0;
            }
        } else {
            return getFromMemory(key)
                    .map(Long::parseLong)
                    .orElse(0L);
        }
    }

    // Memory cache implementation

    private Optional<String> getFromMemory(String key) {
        if (memoryCache == null) return Optional.empty();

        CacheEntry entry = memoryCache.get(key);
        if (entry == null) {
            return Optional.empty();
        }

        if (entry.isExpired()) {
            memoryCache.remove(key);
            return Optional.empty();
        }

        return Optional.of(entry.value);
    }

    private void setInMemory(String key, String value, long ttlSeconds) {
        if (memoryCache == null) return;

        long expiresAt = System.currentTimeMillis() + (ttlSeconds * 1000);
        memoryCache.put(key, new CacheEntry(value, expiresAt));
    }

    private long incrementInMemory(String key, long windowSeconds) {
        if (memoryCache == null) return 0;

        CacheEntry entry = memoryCache.compute(key, (k, existing) -> {
            if (existing == null || existing.isExpired()) {
                long expiresAt = System.currentTimeMillis() + (windowSeconds * 1000);
                return new CacheEntry("1", expiresAt);
            } else {
                long count = Long.parseLong(existing.value) + 1;
                return new CacheEntry(String.valueOf(count), existing.expiresAt);
            }
        });

        return Long.parseLong(entry.value);
    }

    private static class CacheEntry {
        final String value;
        final long expiresAt;

        CacheEntry(String value, long expiresAt) {
            this.value = value;
            this.expiresAt = expiresAt;
        }

        boolean isExpired() {
            return System.currentTimeMillis() > expiresAt;
        }
    }
}
