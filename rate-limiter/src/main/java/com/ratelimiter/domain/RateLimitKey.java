package com.ratelimiter.domain;

import java.util.Objects;

/**
 * Represents a unique key for rate limiting.
 *
 * <p>The key is composed of multiple dimensions that together identify
 * a specific rate limit counter. The key format for Redis storage is:
 * {@code rl:{scope}:{userId}:{endpoint}:{windowStart}}
 *
 * <p>Example keys:
 * <ul>
 *   <li>{@code rl:USER:user123:*:1704067200} - Per user limit</li>
 *   <li>{@code rl:ENDPOINT:*:/api/orders:1704067200} - Per endpoint limit</li>
 *   <li>{@code rl:USER_ENDPOINT:user123:/api/orders:1704067200} - Combined limit</li>
 * </ul>
 */
public record RateLimitKey(
    /**
     * The scope of this rate limit key.
     */
    RateLimitScope scope,

    /**
     * The user identifier (user ID or API key). Null for non-user scopes.
     */
    String userId,

    /**
     * The endpoint path being accessed. Null for non-endpoint scopes.
     */
    String endpoint,

    /**
     * The IP address of the client. Null for non-IP scopes.
     */
    String ipAddress,

    /**
     * The tenant identifier. Null for non-tenant scopes.
     */
    String tenantId,

    /**
     * The rule ID this key is associated with.
     */
    String ruleId
) {

    private static final String WILDCARD = "*";
    private static final String KEY_SEPARATOR = ":";

    /**
     * Creates a rate limit key for a given scope with the provided identifiers.
     */
    public RateLimitKey {
        Objects.requireNonNull(scope, "scope must not be null");
        Objects.requireNonNull(ruleId, "ruleId must not be null");
    }

    /**
     * Creates a GLOBAL scope key.
     */
    public static RateLimitKey global(String ruleId) {
        return new RateLimitKey(RateLimitScope.GLOBAL, null, null, null, null, ruleId);
    }

    /**
     * Creates a USER scope key.
     */
    public static RateLimitKey forUser(String userId, String ruleId) {
        Objects.requireNonNull(userId, "userId must not be null for USER scope");
        return new RateLimitKey(RateLimitScope.USER, userId, null, null, null, ruleId);
    }

    /**
     * Creates an ENDPOINT scope key.
     */
    public static RateLimitKey forEndpoint(String endpoint, String ruleId) {
        Objects.requireNonNull(endpoint, "endpoint must not be null for ENDPOINT scope");
        return new RateLimitKey(RateLimitScope.ENDPOINT, null, endpoint, null, null, ruleId);
    }

    /**
     * Creates a USER_ENDPOINT scope key.
     */
    public static RateLimitKey forUserEndpoint(String userId, String endpoint, String ruleId) {
        Objects.requireNonNull(userId, "userId must not be null for USER_ENDPOINT scope");
        Objects.requireNonNull(endpoint, "endpoint must not be null for USER_ENDPOINT scope");
        return new RateLimitKey(RateLimitScope.USER_ENDPOINT, userId, endpoint, null, null, ruleId);
    }

    /**
     * Creates an IP scope key.
     */
    public static RateLimitKey forIp(String ipAddress, String ruleId) {
        Objects.requireNonNull(ipAddress, "ipAddress must not be null for IP scope");
        return new RateLimitKey(RateLimitScope.IP, null, null, ipAddress, null, ruleId);
    }

    /**
     * Creates a TENANT scope key.
     */
    public static RateLimitKey forTenant(String tenantId, String ruleId) {
        Objects.requireNonNull(tenantId, "tenantId must not be null for TENANT scope");
        return new RateLimitKey(RateLimitScope.TENANT, null, null, null, tenantId, ruleId);
    }

    /**
     * Generates the Redis key for a specific time window.
     *
     * @param keyPrefix the prefix for all rate limit keys (e.g., "rl:")
     * @param windowStart the start timestamp of the window in seconds
     * @return the complete Redis key
     */
    public String toRedisKey(String keyPrefix, long windowStart) {
        StringBuilder key = new StringBuilder(keyPrefix);
        key.append(scope.name()).append(KEY_SEPARATOR);
        key.append(ruleId).append(KEY_SEPARATOR);

        switch (scope) {
            case GLOBAL -> key.append(WILDCARD);
            case USER -> key.append(userId);
            case ENDPOINT -> key.append(normalizeEndpoint(endpoint));
            case USER_ENDPOINT -> key.append(userId).append(KEY_SEPARATOR).append(normalizeEndpoint(endpoint));
            case IP -> key.append(ipAddress);
            case TENANT -> key.append(tenantId);
        }

        key.append(KEY_SEPARATOR).append(windowStart);
        return key.toString();
    }

    /**
     * Generates the base Redis key without the window timestamp.
     * Useful for cache lookups.
     */
    public String toBaseKey(String keyPrefix) {
        StringBuilder key = new StringBuilder(keyPrefix);
        key.append(scope.name()).append(KEY_SEPARATOR);
        key.append(ruleId).append(KEY_SEPARATOR);

        switch (scope) {
            case GLOBAL -> key.append(WILDCARD);
            case USER -> key.append(userId);
            case ENDPOINT -> key.append(normalizeEndpoint(endpoint));
            case USER_ENDPOINT -> key.append(userId).append(KEY_SEPARATOR).append(normalizeEndpoint(endpoint));
            case IP -> key.append(ipAddress);
            case TENANT -> key.append(tenantId);
        }

        return key.toString();
    }

    /**
     * Normalizes endpoint paths for consistent key generation.
     * Replaces path separators and removes query parameters.
     */
    private String normalizeEndpoint(String endpoint) {
        if (endpoint == null) {
            return WILDCARD;
        }
        // Remove query parameters
        int queryIndex = endpoint.indexOf('?');
        if (queryIndex > 0) {
            endpoint = endpoint.substring(0, queryIndex);
        }
        // Replace slashes with underscores for cleaner keys
        return endpoint.replace("/", "_");
    }
}
