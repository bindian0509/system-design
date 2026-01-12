package com.leaderboard.domain.dto;

import java.time.Instant;
import java.util.List;

import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Response DTO for relative/surrounding leaderboard queries.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RelativeLeaderboardResponse {

    /**
     * The player who requested the relative leaderboard
     */
    private String playerId;

    /**
     * The requester's current rank
     */
    private Long playerRank;

    /**
     * The requester's current score
     */
    private Long playerScore;

    /**
     * Surrounding entries (including the requester)
     */
    private List<LeaderboardEntry> entries;

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
     * Total number of players in the leaderboard
     */
    private Long totalPlayers;
}
