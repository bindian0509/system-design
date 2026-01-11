package com.ratelimiter.algorithm;

import com.ratelimiter.domain.RateLimitKey;
import com.ratelimiter.domain.RateLimitResult;
import com.ratelimiter.domain.RateLimitRule;

/**
 * Interface for rate limiting algorithms.
 *
 * <p>Implementations of this interface provide different rate limiting
 * strategies such as sliding window counter, token bucket, or fixed window.
 */
public interface RateLimitAlgorithm {

    /**
     * Returns the algorithm type.
     */
    AlgorithmType getType();

    /**
     * Checks if a request should be allowed and updates counters.
     *
     * @param key the rate limit key identifying the counter
     * @param rule the rate limit rule to apply
     * @param weight the weight of this request (typically 1)
     * @return the result of the rate limit check
     */
    RateLimitResult checkAndIncrement(RateLimitKey key, RateLimitRule rule, int weight);

    /**
     * Checks if a request would be allowed without updating counters.
     *
     * @param key the rate limit key identifying the counter
     * @param rule the rate limit rule to apply
     * @return the result of the rate limit check
     */
    RateLimitResult check(RateLimitKey key, RateLimitRule rule);

    /**
     * Gets the current count for a key without modifying it.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     * @return the current count
     */
    long getCurrentCount(RateLimitKey key, RateLimitRule rule);

    /**
     * Resets the counter for a specific key.
     *
     * @param key the rate limit key
     * @param rule the rate limit rule
     */
    void reset(RateLimitKey key, RateLimitRule rule);

    /**
     * Enum of supported algorithm types.
     */
    enum AlgorithmType {
        SLIDING_WINDOW_COUNTER,
        SLIDING_WINDOW_LOG,
        TOKEN_BUCKET,
        LEAKY_BUCKET,
        FIXED_WINDOW
    }
}
