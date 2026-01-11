package com.ratelimiter.exception;

import com.ratelimiter.domain.RateLimitResult;
import lombok.Getter;

/**
 * Exception thrown when a rate limit is exceeded.
 */
@Getter
public class RateLimitExceededException extends RuntimeException {

    private final RateLimitResult result;

    public RateLimitExceededException(RateLimitResult result) {
        super(buildMessage(result));
        this.result = result;
    }

    public RateLimitExceededException(String message, RateLimitResult result) {
        super(message);
        this.result = result;
    }

    private static String buildMessage(RateLimitResult result) {
        if (result.violatedRuleId() != null) {
            return String.format("Rate limit exceeded for rule '%s': %d/%d requests",
                result.violatedRuleId(), result.currentCount(), result.limit());
        }
        return String.format("Rate limit exceeded: %d/%d requests",
            result.currentCount(), result.limit());
    }
}
