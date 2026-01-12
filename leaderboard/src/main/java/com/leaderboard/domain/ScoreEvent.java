package com.leaderboard.domain;

import java.time.Instant;
import java.util.UUID;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Represents a score update event from a game.
 * This is the core event that flows through Kafka for processing.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ScoreEvent {

    /**
     * Unique identifier for this event
     */
    @Builder.Default
    private String eventId = UUID.randomUUID().toString();

    /**
     * The player who earned the score
     */
    @NotBlank(message = "Player ID is required")
    private String playerId;

    /**
     * The score value (can be points, XP, etc.)
     */
    @NotNull(message = "Score is required")
    @PositiveOrZero(message = "Score must be non-negative")
    private Long score;

    /**
     * Optional game identifier
     */
    private String gameId;

    /**
     * Player's region for regional leaderboards
     */
    private String region;

    /**
     * Timestamp when the score was earned
     */
    @Builder.Default
    private Instant timestamp = Instant.now();

    /**
     * Score update mode
     */
    @Builder.Default
    private ScoreUpdateMode updateMode = ScoreUpdateMode.INCREMENT;

    /**
     * Additional metadata
     */
    private String metadata;

    /**
     * Defines how the score should be applied
     */
    public enum ScoreUpdateMode {
        /**
         * Add to existing score
         */
        INCREMENT,

        /**
         * Replace if higher than existing
         */
        MAX,

        /**
         * Set absolute value
         */
        SET
    }
}
