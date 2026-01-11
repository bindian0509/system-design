package com.ratelimiter.service;

import com.ratelimiter.config.RateLimiterProperties;
import com.ratelimiter.domain.RateLimitRule;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Service for matching requests to applicable rate limit rules.
 *
 * <p>Rules are matched based on:
 * <ul>
 *   <li>Scope (GLOBAL, USER, ENDPOINT, USER_ENDPOINT, IP, TENANT)</li>
 *   <li>Endpoint pattern (regex matching)</li>
 *   <li>Enabled status</li>
 * </ul>
 *
 * <p>Matched rules are returned sorted by priority (lower first).
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RuleMatcherService {

    private final RateLimiterProperties properties;

    // Cache for dynamically added rules
    private final ConcurrentHashMap<String, RateLimitRule> dynamicRules = new ConcurrentHashMap<>();

    /**
     * Gets all applicable rules for a request.
     *
     * @param userId the user ID (may be null)
     * @param endpoint the endpoint path
     * @param ipAddress the client IP address
     * @param tenantId the tenant ID (may be null)
     * @return list of applicable rules sorted by priority
     */
    public List<RateLimitRule> getApplicableRules(String userId, String endpoint,
                                                   String ipAddress, String tenantId) {
        List<RateLimitRule> applicable = new ArrayList<>();

        // Check configured rules
        for (RateLimitRule rule : properties.getRules()) {
            if (isApplicable(rule, userId, endpoint, ipAddress, tenantId)) {
                applicable.add(rule);
            }
        }

        // Check dynamic rules
        for (RateLimitRule rule : dynamicRules.values()) {
            if (isApplicable(rule, userId, endpoint, ipAddress, tenantId)) {
                applicable.add(rule);
            }
        }

        // Sort by priority
        applicable.sort(RateLimitRule::compareTo);

        log.debug("Found {} applicable rules for userId={}, endpoint={}",
            applicable.size(), userId, endpoint);

        return applicable;
    }

    /**
     * Adds a dynamic rule.
     */
    public void addRule(RateLimitRule rule) {
        dynamicRules.put(rule.id(), rule);
        log.info("Added dynamic rule: {}", rule.id());
    }

    /**
     * Updates a dynamic rule.
     */
    public void updateRule(RateLimitRule rule) {
        dynamicRules.put(rule.id(), rule);
        log.info("Updated dynamic rule: {}", rule.id());
    }

    /**
     * Removes a dynamic rule.
     */
    public void removeRule(String ruleId) {
        dynamicRules.remove(ruleId);
        log.info("Removed dynamic rule: {}", ruleId);
    }

    /**
     * Gets a rule by ID.
     */
    public RateLimitRule getRule(String ruleId) {
        // Check configured rules first
        for (RateLimitRule rule : properties.getRules()) {
            if (rule.id().equals(ruleId)) {
                return rule;
            }
        }
        // Check dynamic rules
        return dynamicRules.get(ruleId);
    }

    /**
     * Gets all rules (configured + dynamic).
     */
    public List<RateLimitRule> getAllRules() {
        List<RateLimitRule> all = new ArrayList<>(properties.getRules());
        all.addAll(dynamicRules.values());
        all.sort(RateLimitRule::compareTo);
        return all;
    }

    private boolean isApplicable(RateLimitRule rule, String userId, String endpoint,
                                  String ipAddress, String tenantId) {
        if (!rule.enabled()) {
            return false;
        }

        return switch (rule.scope()) {
            case GLOBAL -> true;
            case USER -> userId != null;
            case ENDPOINT -> endpoint != null && rule.matchesEndpoint(endpoint);
            case USER_ENDPOINT -> userId != null && endpoint != null && rule.matchesEndpoint(endpoint);
            case IP -> ipAddress != null;
            case TENANT -> tenantId != null;
        };
    }
}
