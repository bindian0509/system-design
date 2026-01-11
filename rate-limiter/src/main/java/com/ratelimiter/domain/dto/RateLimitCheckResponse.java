package com.ratelimiter.domain.dto;

import com.ratelimiter.domain.RateLimitResult;

import java.time.Instant;

/**
 * Response DTO for rate limit check results.
 */
public record RateLimitCheckResponse(
    /**
     * Whether the request is allowed.
     */
    boolean allowed,

    /**
     * Current count of requests in the window.
     */
    long currentCount,

    /**
     * Maximum requests allowed in the window.
     */
    long limit,

    /**
     * Remaining requests in the window.
     */
    long remainingRequests,

    /**
     * Time when the window resets (ISO-8601 format).
     */
    Instant windowResetTime,

    /**
     * Seconds until the window resets. Useful for Retry-After header.
     */
    long retryAfterSeconds,

    /**
     * The rule that was violated, if any.
     */
    String violatedRule
) {

    /**
     * Creates a response from a RateLimitResult.
     */
    public static RateLimitCheckResponse from(RateLimitResult result) {
        String violatedRule = result.violatedRuleId() != null
            ? result.violatedRuleId() + ": " + result.violatedRuleName()
            : null;

        return new RateLimitCheckResponse(
            result.allowed(),
            result.currentCount(),
            result.limit(),
            result.remainingRequests(),
            result.windowResetTime(),
            result.retryAfterSeconds(),
            violatedRule
        );
    }
}
