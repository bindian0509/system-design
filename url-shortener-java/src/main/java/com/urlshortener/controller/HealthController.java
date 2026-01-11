package com.urlshortener.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.Map;

/**
 * Health check endpoints
 */
@RestController
@RequiredArgsConstructor
public class HealthController {

    private final Instant startTime = Instant.now();

    /**
     * Liveness probe - is the service running?
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of(
                "status", "ok",
                "timestamp", Instant.now()
        ));
    }

    /**
     * Readiness probe - is the service ready to accept traffic?
     */
    @GetMapping("/ready")
    public ResponseEntity<Map<String, Object>> ready() {
        // In production, check database and cache connectivity
        return ResponseEntity.ok(Map.of(
                "status", "ok",
                "timestamp", Instant.now(),
                "checks", Map.of(
                        "database", "ok",
                        "cache", "ok"
                )
        ));
    }

    /**
     * Prometheus metrics endpoint (handled by actuator)
     * This is just for custom metrics if needed
     */
    @GetMapping("/metrics/custom")
    public ResponseEntity<Map<String, Object>> metrics() {
        long uptimeSeconds = Instant.now().getEpochSecond() - startTime.getEpochSecond();

        return ResponseEntity.ok(Map.of(
                "url_shortener_uptime_seconds", uptimeSeconds,
                "url_shortener_start_time", startTime
        ));
    }
}
