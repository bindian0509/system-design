package com.ratelimiter.domain.dto;

import com.ratelimiter.domain.RateLimitRule;
import com.ratelimiter.domain.RateLimitScope;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.time.Duration;

/**
 * Request DTO for creating or updating rate limit rules.
 */
public record RateLimitRuleRequest(
    /**
     * Unique identifier for the rule.
     */
    @NotBlank(message = "Rule ID is required")
    String id,

    /**
     * Human-readable name for the rule.
     */
    @NotBlank(message = "Rule name is required")
    String name,

    /**
     * The scope at which this rule applies.
     */
    @NotNull(message = "Scope is required")
    RateLimitScope scope,

    /**
     * Regex pattern for matching endpoints.
     */
    String endpointPattern,

    /**
     * Maximum requests allowed in the window.
     */
    @Positive(message = "Max requests must be positive")
    int maxRequests,

    /**
     * Window size in seconds.
     */
    @Positive(message = "Window size must be positive")
    long windowSizeSeconds,

    /**
     * Rule priority. Lower values are evaluated first.
     */
    @Min(value = 0, message = "Priority must be non-negative")
    int priority,

    /**
     * Whether the rule is enabled.
     */
    boolean enabled
) {

    /**
     * Converts this request to a RateLimitRule.
     */
    public RateLimitRule toRule() {
        return RateLimitRule.builder()
            .id(id)
            .name(name)
            .scope(scope)
            .endpointPattern(endpointPattern)
            .maxRequests(maxRequests)
            .windowSize(Duration.ofSeconds(windowSizeSeconds))
            .priority(priority)
            .enabled(enabled)
            .build();
    }
}
