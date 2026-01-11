package com.ratelimiter.domain;

/**
 * Defines the scope at which rate limiting is applied.
 *
 * <p>Scopes are evaluated in priority order, with lower priority numbers
 * being evaluated first. This allows for hierarchical rate limiting where
 * global limits are checked before more specific limits.
 */
public enum RateLimitScope {

    /**
     * Global rate limit applied to all requests regardless of user or endpoint.
     * Typically used to protect the overall system capacity.
     */
    GLOBAL,

    /**
     * Rate limit applied per user (identified by user ID or API key).
     * Controls how many requests a single user can make.
     */
    USER,

    /**
     * Rate limit applied per endpoint (identified by URL pattern).
     * Controls traffic to specific API endpoints.
     */
    ENDPOINT,

    /**
     * Rate limit applied per user per endpoint combination.
     * Most granular control for user-specific endpoint limits.
     */
    USER_ENDPOINT,

    /**
     * Rate limit applied per IP address.
     * Useful for anonymous/unauthenticated traffic control.
     */
    IP,

    /**
     * Rate limit applied per tenant in multi-tenant scenarios.
     * Controls aggregate usage across all users in a tenant.
     */
    TENANT
}
