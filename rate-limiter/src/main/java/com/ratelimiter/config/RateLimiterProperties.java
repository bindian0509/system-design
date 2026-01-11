package com.ratelimiter.config;

import com.ratelimiter.algorithm.RateLimitAlgorithm.AlgorithmType;
import com.ratelimiter.domain.RateLimitRule;
import com.ratelimiter.domain.RateLimitScope;
import jakarta.annotation.PostConstruct;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * Configuration properties for the rate limiter.
 */
@Data
@Component
@ConfigurationProperties(prefix = "rate-limiter")
public class RateLimiterProperties {

    /**
     * Whether rate limiting is enabled.
     */
    private boolean enabled = true;

    /**
     * The rate limiting algorithm to use.
     */
    private AlgorithmType algorithm = AlgorithmType.SLIDING_WINDOW_COUNTER;

    /**
     * Failure mode when Redis is unavailable.
     */
    private FailureMode failureMode = FailureMode.FAIL_OPEN;

    /**
     * Local cache configuration.
     */
    private LocalCacheConfig localCache = new LocalCacheConfig();

    /**
     * Redis configuration.
     */
    private RedisConfig redis = new RedisConfig();

    /**
     * Default rate limit rules.
     */
    private List<RuleConfig> defaultRules = new ArrayList<>();

    /**
     * Parsed rate limit rules (populated from defaultRules on init).
     */
    private List<RateLimitRule> rules = new ArrayList<>();

    @PostConstruct
    public void init() {
        // Convert rule configs to RateLimitRule objects
        for (RuleConfig config : defaultRules) {
            RateLimitRule rule = RateLimitRule.builder()
                .id(config.getId())
                .name(config.getName())
                .scope(config.getScope())
                .endpointPattern(config.getEndpointPattern())
                .maxRequests(config.getMaxRequests())
                .windowSize(Duration.ofSeconds(config.getWindowSizeSeconds()))
                .priority(config.getPriority())
                .enabled(config.isEnabled())
                .build();
            rules.add(rule);
        }

        // Sort by priority
        rules.sort(RateLimitRule::compareTo);
    }

    /**
     * Failure mode options.
     */
    public enum FailureMode {
        /**
         * Allow requests when rate limiter is unavailable.
         */
        FAIL_OPEN,

        /**
         * Reject requests when rate limiter is unavailable.
         */
        FAIL_CLOSED
    }

    /**
     * Local cache configuration.
     */
    @Data
    public static class LocalCacheConfig {
        private boolean enabled = true;
        private long syncIntervalMs = 100;
        private long maxEntries = 100000;
        private long ttlSeconds = 60;
    }

    /**
     * Redis configuration.
     */
    @Data
    public static class RedisConfig {
        private String keyPrefix = "rl:";
        private long timeoutMs = 50;
    }

    /**
     * Rule configuration from YAML.
     */
    @Data
    public static class RuleConfig {
        private String id;
        private String name;
        private RateLimitScope scope;
        private String endpointPattern;
        private int maxRequests;
        private long windowSizeSeconds = 60;
        private int priority = 0;
        private boolean enabled = true;
    }
}
