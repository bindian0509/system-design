package com.leaderboard.controller;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.leaderboard.metrics.LeaderboardMetrics;
import com.leaderboard.websocket.WebSocketSessionManager;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Health check endpoints for the leaderboard service.
 */
@Slf4j
@RestController
@RequiredArgsConstructor
public class HealthController {

    private final StringRedisTemplate redisTemplate;
    private final LeaderboardMetrics metrics;
    private final WebSocketSessionManager webSocketSessionManager;

    /**
     * Liveness probe - is the application running?
     */
    @GetMapping("/health")
    public ResponseEntity<HealthResponse> health() {
        return ResponseEntity.ok(new HealthResponse("ok", Instant.now()));
    }

    /**
     * Readiness probe - is the application ready to accept traffic?
     */
    @GetMapping("/ready")
    public ResponseEntity<ReadinessResponse> ready() {
        Map<String, ComponentStatus> components = new HashMap<>();
        boolean allHealthy = true;

        // Check Redis
        try {
            String pong = redisTemplate.getConnectionFactory().getConnection().ping();
            components.put("redis", new ComponentStatus("healthy", "PONG received"));
        } catch (Exception e) {
            log.warn("Redis health check failed", e);
            components.put("redis", new ComponentStatus("unhealthy", e.getMessage()));
            allHealthy = false;
        }

        // Add metrics info
        components.put("websocket", new ComponentStatus(
            "healthy",
            String.format("%d active connections", webSocketSessionManager.getActiveSessions())
        ));

        String status = allHealthy ? "ready" : "not_ready";
        return allHealthy
            ? ResponseEntity.ok(new ReadinessResponse(status, components, Instant.now()))
            : ResponseEntity.status(503).body(new ReadinessResponse(status, components, Instant.now()));
    }

    /**
     * Detailed system info.
     */
    @GetMapping("/info")
    public ResponseEntity<SystemInfo> info() {
        Runtime runtime = Runtime.getRuntime();

        return ResponseEntity.ok(new SystemInfo(
            "real-time-leaderboard",
            "1.0.0",
            Instant.now(),
            new MemoryInfo(
                runtime.maxMemory(),
                runtime.totalMemory(),
                runtime.freeMemory()
            ),
            new ConnectionInfo(
                webSocketSessionManager.getActiveSessions(),
                webSocketSessionManager.getConnectedPlayers()
            ),
            new MetricsSnapshot(
                (long) metrics.getScoreSubmissions().count(),
                (long) metrics.getScoreEventsProcessed().count(),
                (long) metrics.getLeaderboardQueries().count(),
                metrics.getCacheHitRatio()
            )
        ));
    }

    // Response DTOs
    public record HealthResponse(String status, Instant timestamp) {}

    public record ReadinessResponse(
        String status,
        Map<String, ComponentStatus> components,
        Instant timestamp
    ) {}

    public record ComponentStatus(String status, String details) {}

    public record SystemInfo(
        String application,
        String version,
        Instant timestamp,
        MemoryInfo memory,
        ConnectionInfo connections,
        MetricsSnapshot metrics
    ) {}

    public record MemoryInfo(long maxBytes, long totalBytes, long freeBytes) {}

    public record ConnectionInfo(int websocketSessions, int uniquePlayers) {}

    public record MetricsSnapshot(
        long scoreSubmissions,
        long scoreEventsProcessed,
        long leaderboardQueries,
        double cacheHitRatio
    ) {}
}
