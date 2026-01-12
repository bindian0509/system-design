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
 * Response DTO for leaderboard queries.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LeaderboardResponse {

    /**
     * Leaderboard scope
     */
    private LeaderboardScope scope;

    /**
     * Time window for the leaderboard
     */
    private TimeWindow period;

    /**
     * Region identifier (for regional leaderboards)
     */
    private String region;

    /**
     * Timestamp when this data was retrieved
     */
    private Instant asOf;

    /**
     * Leaderboard entries
     */
    private List<LeaderboardEntry> entries;

    /**
     * Total number of players in this leaderboard
     */
    private Long totalPlayers;

    /**
     * Whether there are more entries available
     */
    private boolean hasMore;

    /**
     * The time window identifier (e.g., "2026-01-12" for daily)
     */
    private String periodIdentifier;
}
