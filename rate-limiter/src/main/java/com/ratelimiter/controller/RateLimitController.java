package com.ratelimiter.controller;

import com.ratelimiter.domain.RateLimitResult;
import com.ratelimiter.domain.RateLimitRule;
import com.ratelimiter.domain.dto.RateLimitCheckRequest;
import com.ratelimiter.domain.dto.RateLimitCheckResponse;
import com.ratelimiter.domain.dto.RateLimitRuleRequest;
import com.ratelimiter.service.RateLimiterService;
import com.ratelimiter.service.RuleMatcherService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * REST controller for rate limit management.
 */
@Slf4j
@RestController
@RequestMapping("/ratelimit")
@RequiredArgsConstructor
public class RateLimitController {

    private final RateLimiterService rateLimiterService;
    private final RuleMatcherService ruleMatcherService;

    /**
     * Checks if a request would be allowed.
     * Does NOT increment counters - use for preview/testing.
     */
    @PostMapping("/check")
    public ResponseEntity<RateLimitCheckResponse> checkRateLimit(
            @Valid @RequestBody RateLimitCheckRequest request) {

        log.debug("Checking rate limit for: {}", request);

        RateLimitResult result = rateLimiterService.getStatus(
            request.userId(),
            request.endpoint(),
            request.ipAddress(),
            request.tenantId()
        );

        RateLimitCheckResponse response = RateLimitCheckResponse.from(result);

        return ResponseEntity.ok()
            .header("X-RateLimit-Limit", String.valueOf(result.limit()))
            .header("X-RateLimit-Remaining", String.valueOf(result.remainingRequests()))
            .header("X-RateLimit-Reset", String.valueOf(result.resetTimeEpochSeconds()))
            .body(response);
    }

    /**
     * Consumes rate limit (increments counter).
     */
    @PostMapping("/consume")
    public ResponseEntity<RateLimitCheckResponse> consumeRateLimit(
            @Valid @RequestBody RateLimitCheckRequest request) {

        log.debug("Consuming rate limit for: {}", request);

        RateLimitResult result = rateLimiterService.checkRateLimit(
            request.userId(),
            request.endpoint(),
            request.ipAddress(),
            request.tenantId(),
            request.effectiveWeight()
        );

        RateLimitCheckResponse response = RateLimitCheckResponse.from(result);

        if (!result.allowed()) {
            return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                .header("X-RateLimit-Limit", String.valueOf(result.limit()))
                .header("X-RateLimit-Remaining", "0")
                .header("X-RateLimit-Reset", String.valueOf(result.resetTimeEpochSeconds()))
                .header("Retry-After", String.valueOf(result.retryAfterSeconds()))
                .body(response);
        }

        return ResponseEntity.ok()
            .header("X-RateLimit-Limit", String.valueOf(result.limit()))
            .header("X-RateLimit-Remaining", String.valueOf(result.remainingRequests()))
            .header("X-RateLimit-Reset", String.valueOf(result.resetTimeEpochSeconds()))
            .body(response);
    }

    /**
     * Gets all configured rules.
     */
    @GetMapping("/rules")
    public ResponseEntity<List<RateLimitRule>> getRules() {
        return ResponseEntity.ok(ruleMatcherService.getAllRules());
    }

    /**
     * Gets a specific rule by ID.
     */
    @GetMapping("/rules/{id}")
    public ResponseEntity<RateLimitRule> getRule(@PathVariable String id) {
        RateLimitRule rule = ruleMatcherService.getRule(id);
        if (rule == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(rule);
    }

    /**
     * Creates a new dynamic rule.
     */
    @PostMapping("/rules")
    public ResponseEntity<RateLimitRule> createRule(
            @Valid @RequestBody RateLimitRuleRequest request) {

        RateLimitRule rule = request.toRule();
        ruleMatcherService.addRule(rule);

        log.info("Created rule: {}", rule.id());
        return ResponseEntity.status(HttpStatus.CREATED).body(rule);
    }

    /**
     * Updates an existing dynamic rule.
     */
    @PutMapping("/rules/{id}")
    public ResponseEntity<RateLimitRule> updateRule(
            @PathVariable String id,
            @Valid @RequestBody RateLimitRuleRequest request) {

        if (!id.equals(request.id())) {
            return ResponseEntity.badRequest().build();
        }

        RateLimitRule rule = request.toRule();
        ruleMatcherService.updateRule(rule);

        log.info("Updated rule: {}", rule.id());
        return ResponseEntity.ok(rule);
    }

    /**
     * Deletes a dynamic rule.
     */
    @DeleteMapping("/rules/{id}")
    public ResponseEntity<Void> deleteRule(@PathVariable String id) {
        ruleMatcherService.removeRule(id);
        log.info("Deleted rule: {}", id);
        return ResponseEntity.noContent().build();
    }

    /**
     * Resets rate limits for a specific user.
     */
    @PostMapping("/reset/user/{userId}")
    public ResponseEntity<Void> resetUserLimits(@PathVariable String userId) {
        rateLimiterService.resetUserLimits(userId);
        log.info("Reset rate limits for user: {}", userId);
        return ResponseEntity.noContent().build();
    }

    /**
     * Gets rate limiter statistics.
     */
    @GetMapping("/stats")
    public ResponseEntity<RateLimiterService.HealthStatus> getStats() {
        return ResponseEntity.ok(rateLimiterService.getHealthStatus());
    }
}
