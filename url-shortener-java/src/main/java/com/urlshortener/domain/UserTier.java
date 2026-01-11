package com.urlshortener.domain;

/**
 * User tier levels with associated capabilities
 */
public enum UserTier {
    FREE(365, 10, 60),           // 1 year TTL, 10 char alias, 60 req/min
    PREMIUM(null, 20, 300),      // No expiry, 20 char alias, 300 req/min
    ENTERPRISE(null, 50, 1000);  // No expiry, 50 char alias, 1000 req/min

    private final Integer defaultTtlDays;
    private final int maxAliasLength;
    private final int requestsPerMinute;

    UserTier(Integer defaultTtlDays, int maxAliasLength, int requestsPerMinute) {
        this.defaultTtlDays = defaultTtlDays;
        this.maxAliasLength = maxAliasLength;
        this.requestsPerMinute = requestsPerMinute;
    }

    public Integer getDefaultTtlDays() {
        return defaultTtlDays;
    }

    public int getMaxAliasLength() {
        return maxAliasLength;
    }

    public int getRequestsPerMinute() {
        return requestsPerMinute;
    }
}
