package com.ratelimiter.domain;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.time.Duration;
import java.util.regex.Pattern;

/**
 * Represents a rate limiting rule configuration.
 *
 * <p>Rules define how rate limiting is applied for specific scopes,
 * with support for endpoint pattern matching and priority ordering.
 *
 * <p>Rules are evaluated in priority order (lower numbers first),
 * allowing hierarchical rate limiting where global limits are
 * checked before more specific user or endpoint limits.
 */
public record RateLimitRule(
    /**
     * Unique identifier for this rule.
     */
    @NotBlank
    String id,

    /**
     * Human-readable name for this rule.
     */
    @NotBlank
    String name,

    /**
     * The scope at which this rule applies.
     */
    @NotNull
    RateLimitScope scope,

    /**
     * Regex pattern for matching endpoints.
     * Only applicable for ENDPOINT and USER_ENDPOINT scopes.
     * Use ".*" to match all endpoints.
     */
    String endpointPattern,

    /**
     * Maximum number of requests allowed in the window.
     */
    @Positive
    int maxRequests,

    /**
     * Size of the time window.
     */
    @NotNull
    Duration windowSize,

    /**
     * Priority of this rule. Lower values are evaluated first.
     * Default is 0.
     */
    @Min(0)
    int priority,

    /**
     * Whether this rule is currently enabled.
     */
    boolean enabled
) implements Comparable<RateLimitRule> {

    // Compiled pattern cache (transient, not part of record identity)
    private static final java.util.concurrent.ConcurrentHashMap<String, Pattern> PATTERN_CACHE =
        new java.util.concurrent.ConcurrentHashMap<>();

    /**
     * Default constructor with validation.
     */
    public RateLimitRule {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("Rule ID must not be blank");
        }
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("Rule name must not be blank");
        }
        if (scope == null) {
            throw new IllegalArgumentException("Scope must not be null");
        }
        if (maxRequests <= 0) {
            throw new IllegalArgumentException("Max requests must be positive");
        }
        if (windowSize == null || windowSize.isNegative() || windowSize.isZero()) {
            throw new IllegalArgumentException("Window size must be positive");
        }
        if (priority < 0) {
            throw new IllegalArgumentException("Priority must be non-negative");
        }

        // Validate endpoint pattern for applicable scopes
        if ((scope == RateLimitScope.ENDPOINT || scope == RateLimitScope.USER_ENDPOINT)
                && endpointPattern != null && !endpointPattern.isEmpty()) {
            try {
                PATTERN_CACHE.computeIfAbsent(endpointPattern, Pattern::compile);
            } catch (Exception e) {
                throw new IllegalArgumentException("Invalid endpoint pattern: " + endpointPattern, e);
            }
        }
    }

    /**
     * Creates a builder for constructing RateLimitRule instances.
     */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Returns the window size in seconds.
     */
    public long windowSizeSeconds() {
        return windowSize.toSeconds();
    }

    /**
     * Checks if the given endpoint matches this rule's pattern.
     *
     * @param endpoint the endpoint to check
     * @return true if the endpoint matches (or no pattern is specified)
     */
    public boolean matchesEndpoint(String endpoint) {
        if (endpointPattern == null || endpointPattern.isEmpty()) {
            return true;
        }
        if (endpoint == null) {
            return false;
        }
        Pattern pattern = PATTERN_CACHE.computeIfAbsent(endpointPattern, Pattern::compile);
        return pattern.matcher(endpoint).matches();
    }

    /**
     * Checks if this rule applies to the given request context.
     *
     * @param userId the user ID (may be null)
     * @param endpoint the endpoint (may be null)
     * @return true if this rule applies
     */
    public boolean appliesTo(String userId, String endpoint) {
        if (!enabled) {
            return false;
        }

        return switch (scope) {
            case GLOBAL -> true;
            case USER -> userId != null;
            case ENDPOINT -> endpoint != null && matchesEndpoint(endpoint);
            case USER_ENDPOINT -> userId != null && endpoint != null && matchesEndpoint(endpoint);
            case IP -> true; // IP is always available from request
            case TENANT -> true; // Tenant check happens elsewhere
        };
    }

    /**
     * Creates a RateLimitKey for this rule with the given identifiers.
     */
    public RateLimitKey createKey(String userId, String endpoint, String ipAddress, String tenantId) {
        return switch (scope) {
            case GLOBAL -> RateLimitKey.global(id);
            case USER -> RateLimitKey.forUser(userId, id);
            case ENDPOINT -> RateLimitKey.forEndpoint(endpoint, id);
            case USER_ENDPOINT -> RateLimitKey.forUserEndpoint(userId, endpoint, id);
            case IP -> RateLimitKey.forIp(ipAddress, id);
            case TENANT -> RateLimitKey.forTenant(tenantId, id);
        };
    }

    @Override
    public int compareTo(RateLimitRule other) {
        return Integer.compare(this.priority, other.priority);
    }

    /**
     * Builder for RateLimitRule.
     */
    public static class Builder {
        private String id;
        private String name;
        private RateLimitScope scope;
        private String endpointPattern;
        private int maxRequests;
        private Duration windowSize;
        private int priority = 0;
        private boolean enabled = true;

        public Builder id(String id) {
            this.id = id;
            return this;
        }

        public Builder name(String name) {
            this.name = name;
            return this;
        }

        public Builder scope(RateLimitScope scope) {
            this.scope = scope;
            return this;
        }

        public Builder endpointPattern(String endpointPattern) {
            this.endpointPattern = endpointPattern;
            return this;
        }

        public Builder maxRequests(int maxRequests) {
            this.maxRequests = maxRequests;
            return this;
        }

        public Builder windowSize(Duration windowSize) {
            this.windowSize = windowSize;
            return this;
        }

        public Builder windowSizeSeconds(long seconds) {
            this.windowSize = Duration.ofSeconds(seconds);
            return this;
        }

        public Builder priority(int priority) {
            this.priority = priority;
            return this;
        }

        public Builder enabled(boolean enabled) {
            this.enabled = enabled;
            return this;
        }

        public RateLimitRule build() {
            return new RateLimitRule(id, name, scope, endpointPattern, maxRequests, windowSize, priority, enabled);
        }
    }
}
