package com.ratelimiter.domain;

import java.time.Instant;
import java.util.Optional;

/**
 * Represents the result of a rate limit check.
 *
 * <p>This record contains all information needed to:
 * <ul>
 *   <li>Determine if the request should be allowed</li>
 *   <li>Populate rate limit response headers</li>
 *   <li>Provide feedback about which rule was violated</li>
 * </ul>
 */
public record RateLimitResult(
    /**
     * Whether the request is allowed to proceed.
     */
    boolean allowed,

    /**
     * The current count of requests in the window (after this request).
     */
    long currentCount,

    /**
     * The maximum number of requests allowed in the window.
     */
    long limit,

    /**
     * The number of requests remaining in the window.
     * Returns 0 if the limit has been exceeded.
     */
    long remainingRequests,

    /**
     * The time when the current window resets.
     */
    Instant windowResetTime,

    /**
     * The ID of the rule that was violated.
     * Null if the request was allowed.
     */
    String violatedRuleId,

    /**
     * The name of the rule that was violated.
     * Null if the request was allowed.
     */
    String violatedRuleName
) {

    /**
     * Creates an allowed result.
     */
    public static RateLimitResult allowed(long currentCount, long limit, Instant resetTime) {
        long remaining = Math.max(0, limit - currentCount);
        return new RateLimitResult(true, currentCount, limit, remaining, resetTime, null, null);
    }

    /**
     * Creates a rejected result.
     */
    public static RateLimitResult rejected(long currentCount, long limit, Instant resetTime,
                                           String ruleId, String ruleName) {
        return new RateLimitResult(false, currentCount, limit, 0, resetTime, ruleId, ruleName);
    }

    /**
     * Creates a result for when the rate limiter is unavailable (fail-open).
     */
    public static RateLimitResult failOpen() {
        return new RateLimitResult(true, 0, Long.MAX_VALUE, Long.MAX_VALUE,
            Instant.now().plusSeconds(60), null, null);
    }

    /**
     * Creates a result for when the rate limiter is unavailable (fail-closed).
     */
    public static RateLimitResult failClosed() {
        return new RateLimitResult(false, Long.MAX_VALUE, 0, 0,
            Instant.now().plusSeconds(60), "SYSTEM", "Rate Limiter Unavailable");
    }

    /**
     * Returns the violated rule ID if present.
     */
    public Optional<String> getViolatedRuleId() {
        return Optional.ofNullable(violatedRuleId);
    }

    /**
     * Returns the retry-after duration in seconds.
     * Returns 0 if the request was allowed.
     */
    public long retryAfterSeconds() {
        if (allowed || windowResetTime == null) {
            return 0;
        }
        long seconds = windowResetTime.getEpochSecond() - Instant.now().getEpochSecond();
        return Math.max(1, seconds);
    }

    /**
     * Returns the reset time as Unix timestamp (seconds).
     */
    public long resetTimeEpochSeconds() {
        return windowResetTime != null ? windowResetTime.getEpochSecond() : 0;
    }

    /**
     * Merges this result with another, returning the most restrictive.
     * If either result is rejected, the merged result is rejected.
     * Otherwise, returns the result with the lower remaining count.
     */
    public RateLimitResult merge(RateLimitResult other) {
        if (other == null) {
            return this;
        }

        // If either is rejected, return the rejected one
        if (!this.allowed && !other.allowed) {
            // Return the one with less remaining (more restrictive)
            return this.remainingRequests <= other.remainingRequests ? this : other;
        }
        if (!this.allowed) {
            return this;
        }
        if (!other.allowed) {
            return other;
        }

        // Both allowed - return the more restrictive (less remaining)
        return this.remainingRequests <= other.remainingRequests ? this : other;
    }
}
