package com.ratelimiter.exception;

/**
 * Exception thrown when the rate limiter is unavailable.
 */
public class RateLimiterUnavailableException extends RuntimeException {

    public RateLimiterUnavailableException(String message) {
        super(message);
    }

    public RateLimiterUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
