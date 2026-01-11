package com.ratelimiter.service;

import com.ratelimiter.algorithm.RateLimitAlgorithm;
import com.ratelimiter.algorithm.RateLimitAlgorithm.AlgorithmType;
import com.ratelimiter.algorithm.SlidingWindowCounter;
import com.ratelimiter.algorithm.FixedWindow;
import com.ratelimiter.algorithm.TokenBucket;
import com.ratelimiter.config.RateLimiterProperties;
import com.ratelimiter.config.RateLimiterProperties.FailureMode;
import com.ratelimiter.domain.RateLimitKey;
import com.ratelimiter.domain.RateLimitResult;
import com.ratelimiter.domain.RateLimitRule;
import com.ratelimiter.metrics.RateLimiterMetrics;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * Main rate limiter service that orchestrates multi-level rate limiting.
 *
 * <p>This service:
 * <ul>
 *   <li>Matches requests to applicable rules</li>
 *   <li>Evaluates rules in priority order</li>
 *   <li>Uses the configured algorithm for each check</li>
 *   <li>Handles failure modes (fail-open/fail-closed)</li>
 *   <li>Records metrics for monitoring</li>
 * </ul>
 */
@Slf4j
@Service
public class RateLimiterService {

    private final RateLimiterProperties properties;
    private final RuleMatcherService ruleMatcherService;
    private final RateLimiterMetrics metrics;
    private final Map<AlgorithmType, RateLimitAlgorithm> algorithms;
    private final CircuitBreakerRegistry circuitBreakerRegistry;

    public RateLimiterService(
            RateLimiterProperties properties,
            RuleMatcherService ruleMatcherService,
            RateLimiterMetrics metrics,
            SlidingWindowCounter slidingWindowCounter,
            FixedWindow fixedWindow,
            TokenBucket tokenBucket,
            CircuitBreakerRegistry circuitBreakerRegistry) {

        this.properties = properties;
        this.ruleMatcherService = ruleMatcherService;
        this.metrics = metrics;
        this.circuitBreakerRegistry = circuitBreakerRegistry;

        // Build algorithm map
        this.algorithms = Map.of(
            AlgorithmType.SLIDING_WINDOW_COUNTER, slidingWindowCounter,
            AlgorithmType.FIXED_WINDOW, fixedWindow,
            AlgorithmType.TOKEN_BUCKET, tokenBucket
        );
    }

    /**
     * Checks if a request should be allowed based on configured rate limits.
     *
     * @param userId the user ID (may be null)
     * @param endpoint the endpoint being accessed
     * @param ipAddress the client IP address
     * @param tenantId the tenant ID (may be null)
     * @param weight the request weight (typically 1)
     * @return the rate limit result
     */
    public RateLimitResult checkRateLimit(String userId, String endpoint,
                                          String ipAddress, String tenantId, int weight) {

        if (!properties.isEnabled()) {
            return RateLimitResult.allowed(0, Long.MAX_VALUE, null);
        }

        long startTime = System.nanoTime();

        try {
            // Get applicable rules
            List<RateLimitRule> rules = ruleMatcherService.getApplicableRules(
                userId, endpoint, ipAddress, tenantId);

            if (rules.isEmpty()) {
                log.debug("No applicable rules for userId={}, endpoint={}", userId, endpoint);
                metrics.recordAllowed("none");
                return RateLimitResult.allowed(0, Long.MAX_VALUE, null);
            }

            // Check each rule in priority order
            RateLimitResult result = null;
            for (RateLimitRule rule : rules) {
                RateLimitResult ruleResult = checkRule(rule, userId, endpoint, ipAddress, tenantId, weight);

                if (!ruleResult.allowed()) {
                    // Request rejected by this rule
                    metrics.recordRejected(rule.id());
                    return ruleResult;
                }

                // Keep the most restrictive allowed result
                result = result == null ? ruleResult : result.merge(ruleResult);
            }

            metrics.recordAllowed(result != null ? result.violatedRuleId() : "none");
            return result != null ? result : RateLimitResult.allowed(0, Long.MAX_VALUE, null);

        } catch (Exception e) {
            log.error("Error checking rate limit for userId={}, endpoint={}: {}",
                userId, endpoint, e.getMessage(), e);
            return handleFailure(e);
        } finally {
            long duration = System.nanoTime() - startTime;
            metrics.recordLatency(duration);
        }
    }

    /**
     * Checks a single rule against the request.
     */
    private RateLimitResult checkRule(RateLimitRule rule, String userId, String endpoint,
                                      String ipAddress, String tenantId, int weight) {

        // Create the rate limit key
        RateLimitKey key = rule.createKey(userId, endpoint, ipAddress, tenantId);

        // Get the algorithm
        RateLimitAlgorithm algorithm = algorithms.get(properties.getAlgorithm());
        if (algorithm == null) {
            log.error("Unknown algorithm: {}, falling back to SLIDING_WINDOW_COUNTER",
                properties.getAlgorithm());
            algorithm = algorithms.get(AlgorithmType.SLIDING_WINDOW_COUNTER);
        }

        // Check and increment
        return algorithm.checkAndIncrement(key, rule, weight);
    }

    /**
     * Handles failures based on the configured failure mode.
     */
    private RateLimitResult handleFailure(Exception e) {
        metrics.recordError();

        if (properties.getFailureMode() == FailureMode.FAIL_OPEN) {
            log.warn("Rate limiter failure, failing OPEN (allowing request): {}", e.getMessage());
            return RateLimitResult.failOpen();
        } else {
            log.warn("Rate limiter failure, failing CLOSED (rejecting request): {}", e.getMessage());
            return RateLimitResult.failClosed();
        }
    }

    /**
     * Gets the current rate limit status for a key without incrementing.
     */
    public RateLimitResult getStatus(String userId, String endpoint,
                                     String ipAddress, String tenantId) {

        List<RateLimitRule> rules = ruleMatcherService.getApplicableRules(
            userId, endpoint, ipAddress, tenantId);

        if (rules.isEmpty()) {
            return RateLimitResult.allowed(0, Long.MAX_VALUE, null);
        }

        RateLimitResult result = null;
        for (RateLimitRule rule : rules) {
            RateLimitKey key = rule.createKey(userId, endpoint, ipAddress, tenantId);
            RateLimitAlgorithm algorithm = algorithms.get(properties.getAlgorithm());

            RateLimitResult ruleResult = algorithm.check(key, rule);
            result = result == null ? ruleResult : result.merge(ruleResult);
        }

        return result != null ? result : RateLimitResult.allowed(0, Long.MAX_VALUE, null);
    }

    /**
     * Resets rate limits for a specific user.
     */
    public void resetUserLimits(String userId) {
        List<RateLimitRule> rules = ruleMatcherService.getAllRules();

        for (RateLimitRule rule : rules) {
            if (rule.scope().name().contains("USER")) {
                RateLimitKey key = rule.createKey(userId, null, null, null);
                RateLimitAlgorithm algorithm = algorithms.get(properties.getAlgorithm());
                algorithm.reset(key, rule);
            }
        }

        log.info("Reset rate limits for user: {}", userId);
    }

    /**
     * Gets the health status of the rate limiter.
     */
    public HealthStatus getHealthStatus() {
        var circuitBreaker = circuitBreakerRegistry.circuitBreaker("redis");
        var state = circuitBreaker.getState();

        return new HealthStatus(
            properties.isEnabled(),
            state.name(),
            properties.getFailureMode().name(),
            properties.getAlgorithm().name()
        );
    }

    /**
     * Health status record.
     */
    public record HealthStatus(
        boolean enabled,
        String circuitBreakerState,
        String failureMode,
        String algorithm
    ) {}
}
