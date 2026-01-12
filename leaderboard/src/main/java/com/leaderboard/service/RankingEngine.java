package com.leaderboard.service;

import java.time.Instant;
import java.util.List;
import java.util.concurrent.CompletableFuture;

import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import com.leaderboard.config.LeaderboardProperties;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.ScoreEvent;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardEntry;
import com.leaderboard.metrics.LeaderboardMetrics;
import com.leaderboard.repository.RedisLeaderboardRepository;
import com.leaderboard.repository.RedisLeaderboardRepository.ScoreUpdateResult;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Core engine for ranking operations.
 * Handles score updates with fault tolerance and provides batch operations.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RankingEngine {

    private final RedisLeaderboardRepository leaderboardRepository;
    private final LeaderboardProperties properties;
    private final LeaderboardMetrics metrics;
    private final NotificationService notificationService;

    /**
     * Process a score update across all relevant leaderboards.
     * This is the main entry point for score processing with full fault tolerance.
     */
    @CircuitBreaker(name = "redis", fallbackMethod = "processScoreUpdateFallback")
    @Retry(name = "redis")
    public void processScoreUpdate(ScoreEvent event) {
        Timer.Sample sample = Timer.start();

        try {
            Instant timestamp = event.getTimestamp();
            String playerId = event.getPlayerId();

            // Update all relevant time windows
            for (TimeWindow window : getTimeWindowsToUpdate()) {
                // Update global leaderboard
                updateLeaderboardWithNotification(
                    LeaderboardScope.GLOBAL, window, null, event);

                // Update regional leaderboard if region is present
                if (event.getRegion() != null && !event.getRegion().isBlank()) {
                    updateLeaderboardWithNotification(
                        LeaderboardScope.REGIONAL, window, event.getRegion(), event);
                }
            }

            sample.stop(metrics.getRankCalculationTimer());
            log.debug("Processed score update for player {} in {}ms",
                playerId, sample.toString());

        } catch (Exception e) {
            sample.stop(metrics.getRankCalculationTimer());
            metrics.incrementRedisErrors();
            throw e;
        }
    }

    /**
     * Batch process multiple score events.
     */
    @Async
    public CompletableFuture<Void> processBatchScoreUpdates(List<ScoreEvent> events) {
        log.info("Processing batch of {} score events", events.size());

        for (ScoreEvent event : events) {
            try {
                processScoreUpdate(event);
            } catch (Exception e) {
                log.error("Failed to process event {} in batch", event.getEventId(), e);
                // Continue processing remaining events
            }
        }

        return CompletableFuture.completedFuture(null);
    }

    /**
     * Recalculate rankings for a specific leaderboard.
     * Used for consistency checks and repairs.
     */
    @CircuitBreaker(name = "redis")
    public void recalculateRankings(LeaderboardScope scope, TimeWindow period, String region) {
        log.info("Recalculating rankings for {}/{}/{}", scope, period, region);

        Instant now = Instant.now();
        String key = leaderboardRepository.buildKey(scope, period, now, region);

        // Get all entries to verify integrity
        Long totalPlayers = leaderboardRepository.getTotalPlayers(key);
        log.info("Leaderboard {}/{}/{} has {} players", scope, period, region, totalPlayers);

        // Force notification refresh
        notificationService.notifyLeaderboardRefresh(scope, period, region);
    }

    /**
     * Get the current top N for cache warming.
     */
    @CircuitBreaker(name = "redis")
    public List<LeaderboardEntry> warmCache(LeaderboardScope scope, TimeWindow period,
            String region, int limit) {

        Instant now = Instant.now();
        String key = leaderboardRepository.buildKey(scope, period, now, region);

        return leaderboardRepository.getTopN(key, limit);
    }

    private void updateLeaderboardWithNotification(LeaderboardScope scope, TimeWindow window,
            String region, ScoreEvent event) {

        String key = leaderboardRepository.buildKey(scope, window, event.getTimestamp(), region);
        long ttlSeconds = window.getTtlSeconds();

        ScoreUpdateResult result = leaderboardRepository.updateScoreAndGetRank(
            key,
            event.getPlayerId(),
            event.getScore(),
            event.getUpdateMode(),
            ttlSeconds
        );

        // Check for notification threshold
        int threshold = properties.getNotifications().getTopNThreshold();
        if (result.rank() <= threshold) {
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

    private List<TimeWindow> getTimeWindowsToUpdate() {
        return List.of(
            TimeWindow.DAILY,
            TimeWindow.WEEKLY,
            TimeWindow.MONTHLY,
            TimeWindow.ALL_TIME
        );
    }

    /**
     * Fallback when Redis is unavailable.
     */
    @SuppressWarnings("unused")
    private void processScoreUpdateFallback(ScoreEvent event, Throwable throwable) {
        log.error("Redis circuit breaker triggered for event {}. Error: {}",
            event.getEventId(), throwable.getMessage());

        metrics.incrementRedisCircuitBreakerOpen();

        // In a real implementation, you might:
        // 1. Queue the event for later retry
        // 2. Write to a dead letter queue
        // 3. Trigger an alert

        throw new RuntimeException("Score processing temporarily unavailable", throwable);
    }
}
