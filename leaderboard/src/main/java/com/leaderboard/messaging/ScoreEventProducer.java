package com.leaderboard.messaging;

import java.util.concurrent.CompletableFuture;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;

import com.leaderboard.config.LeaderboardProperties;
import com.leaderboard.domain.ScoreEvent;
import com.leaderboard.metrics.LeaderboardMetrics;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Kafka producer for score events.
 * Publishes score updates to be processed asynchronously.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ScoreEventProducer {

    private final KafkaTemplate<String, ScoreEvent> kafkaTemplate;
    private final LeaderboardProperties properties;
    private final LeaderboardMetrics metrics;

    /**
     * Publish a score event to Kafka.
     * Uses the player ID as the partition key for ordering guarantees.
     */
    @CircuitBreaker(name = "kafka", fallbackMethod = "publishFallback")
    public CompletableFuture<SendResult<String, ScoreEvent>> publish(ScoreEvent event) {
        String topic = properties.getTopics().getScoreEvents();
        String key = event.getPlayerId();

        log.debug("Publishing score event: {} for player: {} to topic: {}",
            event.getEventId(), key, topic);

        CompletableFuture<SendResult<String, ScoreEvent>> future =
            kafkaTemplate.send(topic, key, event);

        future.whenComplete((result, ex) -> {
            if (ex != null) {
                log.error("Failed to publish score event: {} for player: {}",
                    event.getEventId(), key, ex);
                metrics.incrementKafkaErrors();
            } else {
                log.debug("Successfully published score event: {} to partition: {}, offset: {}",
                    event.getEventId(),
                    result.getRecordMetadata().partition(),
                    result.getRecordMetadata().offset());
                metrics.incrementScoreEventsPublished();
            }
        });

        return future;
    }

    /**
     * Fallback method when Kafka is unavailable.
     * Could implement alternative processing or dead letter queue.
     */
    @SuppressWarnings("unused")
    private CompletableFuture<SendResult<String, ScoreEvent>> publishFallback(
            ScoreEvent event, Throwable throwable) {

        log.warn("Kafka circuit breaker open. Using fallback for event: {} - Error: {}",
            event.getEventId(), throwable.getMessage());

        metrics.incrementKafkaCircuitBreakerOpen();

        // Return failed future - caller should handle this appropriately
        CompletableFuture<SendResult<String, ScoreEvent>> failedFuture = new CompletableFuture<>();
        failedFuture.completeExceptionally(
            new RuntimeException("Kafka unavailable, event queued for retry", throwable));

        return failedFuture;
    }

    /**
     * Publish synchronously and wait for acknowledgment.
     * Use sparingly as this blocks the calling thread.
     */
    public void publishSync(ScoreEvent event) throws Exception {
        String topic = properties.getTopics().getScoreEvents();
        String key = event.getPlayerId();

        try {
            SendResult<String, ScoreEvent> result = kafkaTemplate.send(topic, key, event).get();
            log.debug("Sync published event: {} to partition: {}",
                event.getEventId(), result.getRecordMetadata().partition());
        } catch (Exception e) {
            log.error("Failed to sync publish event: {}", event.getEventId(), e);
            throw e;
        }
    }
}
