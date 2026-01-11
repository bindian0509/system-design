package com.ratelimiter.repository;

import com.ratelimiter.algorithm.TokenBucket.TokenBucketState;
import com.ratelimiter.domain.RateLimitKey;
import com.ratelimiter.domain.RateLimitRule;

/**
 * Repository interface for rate limit counter storage.
 *
 * <p>Implementations may use Redis, in-memory storage, or a combination
 * with local caching for high-performance scenarios.
 */
public interface RateLimitRepository {

    /**
     * Gets the current count for a key in a specific time window.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param windowStart the window start timestamp in seconds
     * @return the current count, or 0 if not found
     */
    long getCount(RateLimitKey key, RateLimitRule rule, long windowStart);

    /**
     * Increments the counter for a key and returns the new count.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param windowStart the window start timestamp in seconds
     * @param amount the amount to increment by
     * @return the new count after increment
     */
    long increment(RateLimitKey key, RateLimitRule rule, long windowStart, int amount);

    /**
     * Resets the counter for a key in a specific time window.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param windowStart the window start timestamp in seconds
     */
    void reset(RateLimitKey key, RateLimitRule rule, long windowStart);

    /**
     * Gets the token bucket state for a key.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @return the token bucket state
     */
    TokenBucketState getTokenBucketState(RateLimitKey key, RateLimitRule rule);

    /**
     * Sets the token bucket state for a key.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param state the new token bucket state
     */
    void setTokenBucketState(RateLimitKey key, RateLimitRule rule, TokenBucketState state);

    /**
     * Executes a sliding window counter check and increment atomically.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @param weight the weight to increment by
     * @return result containing [allowed, count, limit, resetTime]
     */
    SlidingWindowResult checkAndIncrementSlidingWindow(RateLimitKey key, RateLimitRule rule, int weight);

    /**
     * Result of a sliding window counter operation.
     */
    record SlidingWindowResult(boolean allowed, long count, long limit, long resetTimeSeconds) {}
}
