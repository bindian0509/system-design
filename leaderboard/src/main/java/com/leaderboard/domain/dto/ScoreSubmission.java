package com.leaderboard.domain.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import com.leaderboard.domain.ScoreEvent.ScoreUpdateMode;

/**
 * Request DTO for submitting a new score.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ScoreSubmission {

    /**
     * The player submitting the score
     */
    @NotBlank(message = "Player ID is required")
    private String playerId;

    /**
     * The score value
     */
    @NotNull(message = "Score is required")
    @PositiveOrZero(message = "Score must be non-negative")
    private Long score;

    /**
     * Optional game identifier
     */
    private String gameId;

    /**
     * Player's region (e.g., "US-EAST", "EU-WEST", "APAC")
     */
    private String region;

    /**
     * How to apply the score update
     */
    @Builder.Default
    private ScoreUpdateMode updateMode = ScoreUpdateMode.INCREMENT;

    /**
     * Optional metadata (JSON string)
     */
    private String metadata;
}
