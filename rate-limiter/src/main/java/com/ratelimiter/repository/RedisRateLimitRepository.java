package com.ratelimiter.repository;

import com.ratelimiter.algorithm.TokenBucket.TokenBucketState;
import com.ratelimiter.cache.LocalCacheService;
import com.ratelimiter.config.RateLimiterProperties;
import com.ratelimiter.domain.RateLimitKey;
import com.ratelimiter.domain.RateLimitRule;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.scripting.support.ResourceScriptSource;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * Redis-based implementation of RateLimitRepository.
 *
 * <p>This implementation uses Redis for distributed counter storage with:
 * <ul>
 *   <li>Lua scripts for atomic operations</li>
 *   <li>Local caching via Caffeine for high throughput</li>
 *   <li>Circuit breaker for resilience</li>
 * </ul>
 */
@Slf4j
@Repository
@RequiredArgsConstructor
public class RedisRateLimitRepository implements RateLimitRepository {

    private final RedisTemplate<String, String> redisTemplate;
    private final LocalCacheService localCacheService;
    private final RateLimiterProperties properties;

    private RedisScript<List<Long>> slidingWindowScript;
    private RedisScript<List<Long>> tokenBucketScript;

    @PostConstruct
    public void init() {
        // Load Lua scripts
        DefaultRedisScript<List<Long>> swScript = new DefaultRedisScript<>();
        swScript.setScriptSource(new ResourceScriptSource(
            new ClassPathResource("scripts/sliding_window_counter.lua")));
        swScript.setResultType((Class<List<Long>>) (Class<?>) List.class);
        this.slidingWindowScript = swScript;

        DefaultRedisScript<List<Long>> tbScript = new DefaultRedisScript<>();
        tbScript.setScriptSource(new ResourceScriptSource(
            new ClassPathResource("scripts/token_bucket.lua")));
        tbScript.setResultType((Class<List<Long>>) (Class<?>) List.class);
        this.tokenBucketScript = tbScript;

        // Set up sync callback for local cache
        localCacheService.setSyncCallback(this::syncIncrement);

        log.info("Initialized Redis rate limit repository");
    }

    @Override
    @CircuitBreaker(name = "redis", fallbackMethod = "getCountFallback")
    public long getCount(RateLimitKey key, RateLimitRule rule, long windowStart) {
        // Try local cache first
        Long cachedCount = localCacheService.getCount(key, rule, windowStart);
        if (cachedCount != null) {
            return cachedCount;
        }

        // Fetch from Redis
        String redisKey = key.toRedisKey(properties.getRedis().getKeyPrefix(), windowStart);
        String value = redisTemplate.opsForValue().get(redisKey);

        long count = value != null ? Long.parseLong(value) : 0;

        // Update local cache
        localCacheService.updateFromRedis(key, rule, windowStart, count);

        return count;
    }

    /**
     * Fallback when Redis is unavailable for getCount.
     */
    @SuppressWarnings("unused")
    private long getCountFallback(RateLimitKey key, RateLimitRule rule, long windowStart, Exception e) {
        log.warn("Redis unavailable for getCount, using local cache only: {}", e.getMessage());
        Long cachedCount = localCacheService.getCount(key, rule, windowStart);
        return cachedCount != null ? cachedCount : 0;
    }

    @Override
    @CircuitBreaker(name = "redis", fallbackMethod = "incrementFallback")
    public long increment(RateLimitKey key, RateLimitRule rule, long windowStart, int amount) {
        // Increment local cache immediately for low latency
        long localCount = localCacheService.incrementLocal(key, rule, windowStart, amount);

        // The actual Redis increment happens via the sync callback
        // For immediate consistency, we can also do it synchronously here
        if (!properties.getLocalCache().isEnabled()) {
            String redisKey = key.toRedisKey(properties.getRedis().getKeyPrefix(), windowStart);
            Long newValue = redisTemplate.opsForValue().increment(redisKey, amount);

            // Set expiry
            redisTemplate.expire(redisKey, rule.windowSizeSeconds() * 2, TimeUnit.SECONDS);

            return newValue != null ? newValue : amount;
        }

        return localCount;
    }

    /**
     * Fallback when Redis is unavailable for increment.
     */
    @SuppressWarnings("unused")
    private long incrementFallback(RateLimitKey key, RateLimitRule rule, long windowStart, int amount, Exception e) {
        log.warn("Redis unavailable for increment, using local cache only: {}", e.getMessage());
        return localCacheService.incrementLocal(key, rule, windowStart, amount);
    }

    @Override
    @CircuitBreaker(name = "redis")
    public void reset(RateLimitKey key, RateLimitRule rule, long windowStart) {
        String redisKey = key.toRedisKey(properties.getRedis().getKeyPrefix(), windowStart);
        redisTemplate.delete(redisKey);
    }

    @Override
    @CircuitBreaker(name = "redis", fallbackMethod = "getTokenBucketStateFallback")
    public TokenBucketState getTokenBucketState(RateLimitKey key, RateLimitRule rule) {
        String redisKey = key.toBaseKey(properties.getRedis().getKeyPrefix()) + ":bucket";

        List<Object> values = redisTemplate.opsForHash().multiGet(
            redisKey,
            List.of("tokens", "last_refill")
        );

        if (values.get(0) == null) {
            return TokenBucketState.initial(rule.maxRequests());
        }

        long tokens = Long.parseLong((String) values.get(0));
        long lastRefill = Long.parseLong((String) values.get(1));

        return new TokenBucketState(tokens, lastRefill);
    }

    /**
     * Fallback when Redis is unavailable for getTokenBucketState.
     */
    @SuppressWarnings("unused")
    private TokenBucketState getTokenBucketStateFallback(RateLimitKey key, RateLimitRule rule, Exception e) {
        log.warn("Redis unavailable for getTokenBucketState: {}", e.getMessage());
        return TokenBucketState.initial(rule.maxRequests());
    }

    @Override
    @CircuitBreaker(name = "redis")
    public void setTokenBucketState(RateLimitKey key, RateLimitRule rule, TokenBucketState state) {
        String redisKey = key.toBaseKey(properties.getRedis().getKeyPrefix()) + ":bucket";

        redisTemplate.opsForHash().putAll(redisKey, java.util.Map.of(
            "tokens", String.valueOf(state.tokens()),
            "last_refill", String.valueOf(state.lastRefillTime())
        ));

        redisTemplate.expire(redisKey, rule.windowSizeSeconds() * 2, TimeUnit.SECONDS);
    }

    @Override
    @CircuitBreaker(name = "redis", fallbackMethod = "checkAndIncrementSlidingWindowFallback")
    public SlidingWindowResult checkAndIncrementSlidingWindow(RateLimitKey key, RateLimitRule rule, int weight) {
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();
        long currentWindowStart = (now / windowSizeSeconds) * windowSizeSeconds;
        long previousWindowStart = currentWindowStart - windowSizeSeconds;

        String currentKey = key.toRedisKey(properties.getRedis().getKeyPrefix(), currentWindowStart);
        String previousKey = key.toRedisKey(properties.getRedis().getKeyPrefix(), previousWindowStart);

        List<Long> result = redisTemplate.execute(
            slidingWindowScript,
            List.of(currentKey, previousKey),
            String.valueOf(windowSizeSeconds),
            String.valueOf(now),
            String.valueOf(rule.maxRequests()),
            String.valueOf(weight)
        );

        if (result == null || result.size() < 4) {
            log.error("Unexpected result from sliding window script: {}", result);
            return new SlidingWindowResult(true, 0, rule.maxRequests(), currentWindowStart + windowSizeSeconds);
        }

        boolean allowed = result.get(0) == 1;
        long count = result.get(1);
        long limit = result.get(2);
        long resetTime = result.get(3);

        // Update local cache with new count
        if (allowed) {
            localCacheService.updateFromRedis(key, rule, currentWindowStart,
                getCount(key, rule, currentWindowStart));
        }

        return new SlidingWindowResult(allowed, count, limit, resetTime);
    }

    /**
     * Fallback when Redis is unavailable for checkAndIncrementSlidingWindow.
     */
    @SuppressWarnings("unused")
    private SlidingWindowResult checkAndIncrementSlidingWindowFallback(
            RateLimitKey key, RateLimitRule rule, int weight, Exception e) {
        log.warn("Redis unavailable for checkAndIncrementSlidingWindow: {}", e.getMessage());

        // Fall back to local cache only
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();
        long currentWindowStart = (now / windowSizeSeconds) * windowSizeSeconds;

        Long cachedCount = localCacheService.getCount(key, rule, currentWindowStart);
        long count = cachedCount != null ? cachedCount : 0;

        if (count + weight > rule.maxRequests()) {
            return new SlidingWindowResult(false, count, rule.maxRequests(), currentWindowStart + windowSizeSeconds);
        }

        long newCount = localCacheService.incrementLocal(key, rule, currentWindowStart, weight);
        return new SlidingWindowResult(true, newCount, rule.maxRequests(), currentWindowStart + windowSizeSeconds);
    }

    /**
     * Syncs a buffered increment to Redis.
     * Called by the LocalCacheService during periodic sync.
     */
    private void syncIncrement(String redisKey, Long increment) {
        try {
            redisTemplate.opsForValue().increment(redisKey, increment);
            // Note: We don't set expiry here as it should already be set
        } catch (Exception e) {
            log.warn("Failed to sync increment to Redis for key {}: {}", redisKey, e.getMessage());
            throw e;
        }
    }
}
