package com.leaderboard.domain.dto;

import java.time.Instant;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Response DTO for score submission.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ScoreSubmissionResponse {

    /**
     * Unique event ID for tracking
     */
    private String eventId;

    /**
     * Status of the submission
     */
    private SubmissionStatus status;

    /**
     * Timestamp when the event was received
     */
    private Instant receivedAt;

    /**
     * Optional message
     */
    private String message;

    public enum SubmissionStatus {
        QUEUED,
        ACCEPTED,
        REJECTED
    }

    public static ScoreSubmissionResponse queued(String eventId) {
        return ScoreSubmissionResponse.builder()
            .eventId(eventId)
            .status(SubmissionStatus.QUEUED)
            .receivedAt(Instant.now())
            .message("Score event queued for processing")
            .build();
    }

    public static ScoreSubmissionResponse rejected(String reason) {
        return ScoreSubmissionResponse.builder()
            .status(SubmissionStatus.REJECTED)
            .receivedAt(Instant.now())
            .message(reason)
            .build();
    }
}
