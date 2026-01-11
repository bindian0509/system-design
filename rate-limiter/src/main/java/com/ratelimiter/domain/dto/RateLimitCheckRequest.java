package com.ratelimiter.domain.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * Request DTO for checking rate limits via the API.
 */
public record RateLimitCheckRequest(
    /**
     * The user ID or API key. Optional for IP-only rate limiting.
     */
    String userId,

    /**
     * The endpoint being accessed.
     */
    @NotBlank(message = "Endpoint is required")
    String endpoint,

    /**
     * The IP address of the client. Optional, will be extracted from request if not provided.
     */
    String ipAddress,

    /**
     * The tenant ID for multi-tenant scenarios. Optional.
     */
    String tenantId,

    /**
     * Optional request weight. Defaults to 1.
     * Useful for endpoints that should consume more of the rate limit.
     */
    Integer weight
) {

    /**
     * Returns the effective weight, defaulting to 1 if not specified.
     */
    public int effectiveWeight() {
        return weight != null && weight > 0 ? weight : 1;
    }
}
