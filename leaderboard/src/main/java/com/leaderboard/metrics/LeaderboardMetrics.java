package com.leaderboard.metrics;

import org.springframework.stereotype.Component;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import lombok.Getter;

/**
 * Centralized metrics for the leaderboard system.
 * Exposes Prometheus metrics for monitoring and alerting.
 */
@Component
@Getter
public class LeaderboardMetrics {

    private static final String METRIC_PREFIX = "leaderboard_";

    // Counters
    private final Counter scoreSubmissions;
    private final Counter scoreSubmissionErrors;
    private final Counter scoreEventsPublished;
    private final Counter scoreEventsProcessed;
    private final Counter scoreProcessingErrors;
    private final Counter kafkaErrors;
    private final Counter kafkaCircuitBreakerOpen;
    private final Counter redisErrors;
    private final Counter redisCircuitBreakerOpen;
    private final Counter leaderboardQueries;
    private final Counter cacheHits;
    private final Counter cacheMisses;
    private final Counter websocketConnections;
    private final Counter websocketDisconnections;
    private final Counter notificationsSent;

    // Timers
    private final Timer scoreSubmissionTimer;
    private final Timer scoreProcessingTimer;
    private final Timer leaderboardQueryTimer;
    private final Timer redisOperationTimer;
    private final Timer rankCalculationTimer;

    // Gauges (values are updated externally)
    private volatile long activeWebsocketConnections = 0;
    private volatile long kafkaConsumerLag = 0;

    public LeaderboardMetrics(MeterRegistry registry) {
        // Score submission counters
        this.scoreSubmissions = Counter.builder(METRIC_PREFIX + "score_submissions_total")
            .description("Total score submissions received")
            .register(registry);

        this.scoreSubmissionErrors = Counter.builder(METRIC_PREFIX + "score_submission_errors_total")
            .description("Total score submission errors")
            .register(registry);

        this.scoreEventsPublished = Counter.builder(METRIC_PREFIX + "score_events_published_total")
            .description("Total score events published to Kafka")
            .register(registry);

        this.scoreEventsProcessed = Counter.builder(METRIC_PREFIX + "score_events_processed_total")
            .description("Total score events processed from Kafka")
            .register(registry);

        this.scoreProcessingErrors = Counter.builder(METRIC_PREFIX + "score_processing_errors_total")
            .description("Total score processing errors")
            .register(registry);

        // Kafka counters
        this.kafkaErrors = Counter.builder(METRIC_PREFIX + "kafka_errors_total")
            .description("Total Kafka errors")
            .register(registry);

        this.kafkaCircuitBreakerOpen = Counter.builder(METRIC_PREFIX + "kafka_circuit_breaker_open_total")
            .description("Times Kafka circuit breaker opened")
            .register(registry);

        // Redis counters
        this.redisErrors = Counter.builder(METRIC_PREFIX + "redis_errors_total")
            .description("Total Redis errors")
            .register(registry);

        this.redisCircuitBreakerOpen = Counter.builder(METRIC_PREFIX + "redis_circuit_breaker_open_total")
            .description("Times Redis circuit breaker opened")
            .register(registry);

        // Query counters
        this.leaderboardQueries = Counter.builder(METRIC_PREFIX + "queries_total")
            .description("Total leaderboard queries")
            .register(registry);

        this.cacheHits = Counter.builder(METRIC_PREFIX + "cache_hits_total")
            .description("Total cache hits")
            .register(registry);

        this.cacheMisses = Counter.builder(METRIC_PREFIX + "cache_misses_total")
            .description("Total cache misses")
            .register(registry);

        // WebSocket counters
        this.websocketConnections = Counter.builder(METRIC_PREFIX + "websocket_connections_total")
            .description("Total WebSocket connections")
            .register(registry);

        this.websocketDisconnections = Counter.builder(METRIC_PREFIX + "websocket_disconnections_total")
            .description("Total WebSocket disconnections")
            .register(registry);

        this.notificationsSent = Counter.builder(METRIC_PREFIX + "notifications_sent_total")
            .description("Total notifications sent")
            .register(registry);

        // Timers
        this.scoreSubmissionTimer = Timer.builder(METRIC_PREFIX + "score_submission_duration_seconds")
            .description("Score submission duration")
            .register(registry);

        this.scoreProcessingTimer = Timer.builder(METRIC_PREFIX + "score_processing_duration_seconds")
            .description("Score processing duration")
            .register(registry);

        this.leaderboardQueryTimer = Timer.builder(METRIC_PREFIX + "query_duration_seconds")
            .description("Leaderboard query duration")
            .register(registry);

        this.redisOperationTimer = Timer.builder(METRIC_PREFIX + "redis_operation_duration_seconds")
            .description("Redis operation duration")
            .register(registry);

        this.rankCalculationTimer = Timer.builder(METRIC_PREFIX + "rank_calculation_duration_seconds")
            .description("Rank calculation duration")
            .register(registry);

        // Gauges
        Gauge.builder(METRIC_PREFIX + "websocket_active_connections",
                this, LeaderboardMetrics::getActiveWebsocketConnections)
            .description("Current active WebSocket connections")
            .register(registry);

        Gauge.builder(METRIC_PREFIX + "kafka_consumer_lag",
                this, LeaderboardMetrics::getKafkaConsumerLag)
            .description("Kafka consumer lag")
            .register(registry);
    }

    // Increment methods
    public void incrementScoreSubmissions() {
        scoreSubmissions.increment();
    }

    public void incrementScoreSubmissionErrors() {
        scoreSubmissionErrors.increment();
    }

    public void incrementScoreEventsPublished() {
        scoreEventsPublished.increment();
    }

    public void incrementScoreEventsProcessed() {
        scoreEventsProcessed.increment();
    }

    public void incrementScoreProcessingErrors() {
        scoreProcessingErrors.increment();
    }

    public void incrementKafkaErrors() {
        kafkaErrors.increment();
    }

    public void incrementKafkaCircuitBreakerOpen() {
        kafkaCircuitBreakerOpen.increment();
    }

    public void incrementRedisErrors() {
        redisErrors.increment();
    }

    public void incrementRedisCircuitBreakerOpen() {
        redisCircuitBreakerOpen.increment();
    }

    public void incrementLeaderboardQueries() {
        leaderboardQueries.increment();
    }

    public void incrementCacheHits() {
        cacheHits.increment();
    }

    public void incrementCacheMisses() {
        cacheMisses.increment();
    }

    public void incrementWebsocketConnections() {
        websocketConnections.increment();
        activeWebsocketConnections++;
    }

    public void incrementWebsocketDisconnections() {
        websocketDisconnections.increment();
        if (activeWebsocketConnections > 0) {
            activeWebsocketConnections--;
        }
    }

    public void incrementNotificationsSent() {
        notificationsSent.increment();
    }

    // Gauge setters
    public void setActiveWebsocketConnections(long count) {
        this.activeWebsocketConnections = count;
    }

    public void setKafkaConsumerLag(long lag) {
        this.kafkaConsumerLag = lag;
    }

    public long getActiveWebsocketConnections() {
        return activeWebsocketConnections;
    }

    public long getKafkaConsumerLag() {
        return kafkaConsumerLag;
    }

    // Calculate cache hit ratio
    public double getCacheHitRatio() {
        double hits = cacheHits.count();
        double misses = cacheMisses.count();
        double total = hits + misses;
        return total > 0 ? hits / total : 0.0;
    }
}
