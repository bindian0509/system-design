package com.leaderboard.messaging;

import java.time.Instant;
import java.util.List;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Component;

import com.leaderboard.config.LeaderboardProperties;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.ScoreEvent;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.metrics.LeaderboardMetrics;
import com.leaderboard.repository.RedisLeaderboardRepository;
import com.leaderboard.repository.RedisLeaderboardRepository.ScoreUpdateResult;
import com.leaderboard.service.NotificationService;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Kafka consumer for processing score events.
 * Updates Redis leaderboards and triggers notifications.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ScoreEventConsumer {

    private final RedisLeaderboardRepository leaderboardRepository;
    private final NotificationService notificationService;
    private final LeaderboardProperties properties;
    private final LeaderboardMetrics metrics;

    // Default time windows to update
    private static final List<TimeWindow> DEFAULT_TIME_WINDOWS = List.of(
        TimeWindow.DAILY,
        TimeWindow.WEEKLY,
        TimeWindow.MONTHLY,
        TimeWindow.ALL_TIME
    );

    /**
     * Process score events from Kafka.
     */
    @KafkaListener(
        topics = "${leaderboard.topics.score-events}",
        groupId = "${spring.kafka.consumer.group-id}",
        containerFactory = "kafkaListenerContainerFactory"
    )
    public void consume(
            @Payload ScoreEvent event,
            @Header(KafkaHeaders.RECEIVED_PARTITION) int partition,
            @Header(KafkaHeaders.OFFSET) long offset,
            Acknowledgment ack) {

        Timer.Sample sample = Timer.start();

        try {
            log.debug("Processing score event: {} from partition: {}, offset: {}",
                event.getEventId(), partition, offset);

            processScoreEvent(event);

            // Acknowledge successful processing
            ack.acknowledge();

            metrics.incrementScoreEventsProcessed();
            sample.stop(metrics.getScoreProcessingTimer());

            log.debug("Successfully processed event: {}", event.getEventId());

        } catch (Exception e) {
            log.error("Failed to process score event: {}", event.getEventId(), e);
            metrics.incrementScoreProcessingErrors();
            sample.stop(metrics.getScoreProcessingTimer());

            // Don't acknowledge - will be redelivered
            // Consider implementing dead letter queue for repeated failures
            throw e;
        }
    }

    /**
     * Process a single score event across all relevant leaderboards.
     */
    @CircuitBreaker(name = "redis", fallbackMethod = "processEventFallback")
    private void processScoreEvent(ScoreEvent event) {
        Instant timestamp = event.getTimestamp();
        String playerId = event.getPlayerId();
        long score = event.getScore();

        // Update global leaderboards for each time window
        for (TimeWindow window : DEFAULT_TIME_WINDOWS) {
            updateLeaderboard(
                LeaderboardScope.GLOBAL,
                window,
                null,
                event
            );
        }

        // Update regional leaderboards if region is specified
        if (event.getRegion() != null && !event.getRegion().isBlank()) {
            for (TimeWindow window : DEFAULT_TIME_WINDOWS) {
                updateLeaderboard(
                    LeaderboardScope.REGIONAL,
                    window,
                    event.getRegion(),
                    event
                );
            }
        }

        log.info("Updated leaderboards for player: {} with score: {}", playerId, score);
    }

    /**
     * Update a specific leaderboard and check for notifications.
     */
    private void updateLeaderboard(LeaderboardScope scope, TimeWindow window,
            String region, ScoreEvent event) {

        String key = leaderboardRepository.buildKey(scope, window, event.getTimestamp(), region);
        long ttlSeconds = window.getTtlSeconds();

        // Atomic update and rank retrieval
        ScoreUpdateResult result = leaderboardRepository.updateScoreAndGetRank(
            key,
            event.getPlayerId(),
            event.getScore(),
            event.getUpdateMode(),
            ttlSeconds
        );

        log.debug("Updated {}/{} leaderboard for player: {} - rank: {}/{}",
            scope, window, event.getPlayerId(), result.rank(), result.totalPlayers());

        // Check if player entered top N (for notifications)
        int topNThreshold = properties.getNotifications().getTopNThreshold();
        if (result.rank() <= topNThreshold) {
            notificationService.notifyRankChange(
                event.getPlayerId(),
                result.rank(),
                result.newScore(),
                scope,
                window,
                region
            );
        }
    }

    /**
     * Fallback when Redis circuit breaker is open.
     */
    @SuppressWarnings("unused")
    private void processEventFallback(ScoreEvent event, Throwable throwable) {
        log.warn("Redis circuit breaker open. Event {} will be retried later. Error: {}",
            event.getEventId(), throwable.getMessage());

        metrics.incrementRedisCircuitBreakerOpen();

        // Rethrow to prevent acknowledgment
        throw new RuntimeException("Redis unavailable", throwable);
    }
}
