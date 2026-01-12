package com.leaderboard.domain.dto;

import java.time.Instant;

import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Response DTO for player rank queries.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PlayerRankResponse {

    /**
     * Player's unique identifier
     */
    private String playerId;

    /**
     * Player's display name
     */
    private String playerName;

    /**
     * Player's current rank (1-indexed)
     */
    private Long rank;

    /**
     * Player's current score
     */
    private Long score;

    /**
     * Player's percentile (e.g., 97.5 means top 2.5%)
     */
    private Double percentile;

    /**
     * Total number of players in the leaderboard
     */
    private Long totalPlayers;

    /**
     * Leaderboard scope
     */
    private LeaderboardScope scope;

    /**
     * Time window
     */
    private TimeWindow period;

    /**
     * Region (for regional leaderboards)
     */
    private String region;

    /**
     * Timestamp when this data was retrieved
     */
    private Instant asOf;

    /**
     * Calculate percentile based on rank and total players
     */
    public static double calculatePercentile(long rank, long totalPlayers) {
        if (totalPlayers == 0) return 0.0;
        return ((double) (totalPlayers - rank + 1) / totalPlayers) * 100.0;
    }
}
