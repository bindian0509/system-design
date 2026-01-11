package com.ratelimiter.controller;

import com.ratelimiter.cache.LocalCacheService;
import com.ratelimiter.service.RateLimiterService;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

/**
 * Health check endpoints.
 */
@RestController
@RequiredArgsConstructor
public class HealthController {

    private final RateLimiterService rateLimiterService;
    private final LocalCacheService localCacheService;
    private final CircuitBreakerRegistry circuitBreakerRegistry;

    /**
     * Basic health check.
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        Map<String, Object> health = new HashMap<>();
        health.put("status", "UP");
        health.put("service", "distributed-rate-limiter");

        var status = rateLimiterService.getHealthStatus();
        health.put("rateLimiter", Map.of(
            "enabled", status.enabled(),
            "algorithm", status.algorithm(),
            "failureMode", status.failureMode(),
            "circuitBreaker", status.circuitBreakerState()
        ));

        return ResponseEntity.ok(health);
    }

    /**
     * Readiness check - includes dependency checks.
     */
    @GetMapping("/ready")
    public ResponseEntity<Map<String, Object>> ready() {
        Map<String, Object> ready = new HashMap<>();

        var circuitBreaker = circuitBreakerRegistry.circuitBreaker("redis");
        boolean redisHealthy = circuitBreaker.getState() != io.github.resilience4j.circuitbreaker.CircuitBreaker.State.OPEN;

        ready.put("status", redisHealthy ? "UP" : "DEGRADED");
        ready.put("redis", Map.of(
            "status", redisHealthy ? "UP" : "DOWN",
            "circuitBreaker", circuitBreaker.getState().name()
        ));

        var cacheStats = localCacheService.getStats();
        ready.put("cache", Map.of(
            "hitRate", String.format("%.2f%%", cacheStats.hitRate() * 100),
            "size", cacheStats.estimatedSize(),
            "pendingSyncs", cacheStats.pendingSyncCount()
        ));

        return ResponseEntity.ok(ready);
    }
}
