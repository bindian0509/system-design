package com.leaderboard.domain.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Represents a single entry in the leaderboard.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LeaderboardEntry {

    /**
     * Player's rank (1-indexed)
     */
    private Long rank;

    /**
     * Player's unique identifier
     */
    private String playerId;

    /**
     * Player's display name
     */
    private String playerName;

    /**
     * Player's avatar URL
     */
    private String avatarUrl;

    /**
     * Player's score
     */
    private Long score;

    /**
     * Indicates if this is the requesting player (for relative leaderboards)
     */
    @Builder.Default
    private boolean isRequester = false;

    /**
     * Player's region
     */
    private String region;

    /**
     * Create a basic entry without player profile info
     */
    public static LeaderboardEntry basic(long rank, String playerId, long score) {
        return LeaderboardEntry.builder()
            .rank(rank)
            .playerId(playerId)
            .score(score)
            .build();
    }
}
