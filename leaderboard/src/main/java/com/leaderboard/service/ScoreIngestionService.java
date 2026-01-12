package com.leaderboard.service;

import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

import org.springframework.stereotype.Service;

import com.leaderboard.domain.ScoreEvent;
import com.leaderboard.domain.dto.ScoreSubmission;
import com.leaderboard.domain.dto.ScoreSubmissionResponse;
import com.leaderboard.messaging.ScoreEventProducer;
import com.leaderboard.metrics.LeaderboardMetrics;

import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Service for ingesting score submissions.
 * Validates input and publishes to Kafka for async processing.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ScoreIngestionService {

    private final ScoreEventProducer scoreEventProducer;
    private final LeaderboardMetrics metrics;

    /**
     * Submit a new score.
     * The score is validated and published to Kafka for asynchronous processing.
     */
    public ScoreSubmissionResponse submitScore(ScoreSubmission submission) {
        Timer.Sample sample = Timer.start();

        try {
            // Create score event from submission
            ScoreEvent event = ScoreEvent.builder()
                .eventId(UUID.randomUUID().toString())
                .playerId(submission.getPlayerId())
                .score(submission.getScore())
                .gameId(submission.getGameId())
                .region(submission.getRegion())
                .updateMode(submission.getUpdateMode())
                .metadata(submission.getMetadata())
                .timestamp(Instant.now())
                .build();

            log.info("Submitting score: {} for player: {} with mode: {}",
                event.getScore(), event.getPlayerId(), event.getUpdateMode());

            // Publish to Kafka
            CompletableFuture<?> future = scoreEventProducer.publish(event);

            // Don't wait for the result - return immediately
            future.exceptionally(ex -> {
                log.error("Async publish failed for event: {}", event.getEventId(), ex);
                return null;
            });

            metrics.incrementScoreSubmissions();
            sample.stop(metrics.getScoreSubmissionTimer());

            return ScoreSubmissionResponse.queued(event.getEventId());

        } catch (Exception e) {
            log.error("Failed to submit score for player: {}", submission.getPlayerId(), e);
            metrics.incrementScoreSubmissionErrors();
            sample.stop(metrics.getScoreSubmissionTimer());
            return ScoreSubmissionResponse.rejected("Failed to queue score: " + e.getMessage());
        }
    }

    /**
     * Submit a score synchronously (blocking).
     * Use only when you need confirmation of delivery.
     */
    public ScoreSubmissionResponse submitScoreSync(ScoreSubmission submission) throws Exception {
        ScoreEvent event = ScoreEvent.builder()
            .eventId(UUID.randomUUID().toString())
            .playerId(submission.getPlayerId())
            .score(submission.getScore())
            .gameId(submission.getGameId())
            .region(submission.getRegion())
            .updateMode(submission.getUpdateMode())
            .metadata(submission.getMetadata())
            .timestamp(Instant.now())
            .build();

        scoreEventProducer.publishSync(event);

        return ScoreSubmissionResponse.builder()
            .eventId(event.getEventId())
            .status(ScoreSubmissionResponse.SubmissionStatus.ACCEPTED)
            .receivedAt(Instant.now())
            .message("Score event accepted and acknowledged by Kafka")
            .build();
    }

    /**
     * Batch submit multiple scores.
     */
    public void submitScoresBatch(Iterable<ScoreSubmission> submissions) {
        for (ScoreSubmission submission : submissions) {
            try {
                submitScore(submission);
            } catch (Exception e) {
                log.error("Failed to submit score in batch for player: {}",
                    submission.getPlayerId(), e);
            }
        }
    }
}
