package com.leaderboard.domain.dto;

import java.time.Instant;

import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Notification DTO sent via WebSocket when a player's rank changes.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RankUpdateNotification {

    /**
     * Type of notification
     */
    private NotificationType type;

    /**
     * Player whose rank changed
     */
    private String playerId;

    /**
     * Player's display name
     */
    private String playerName;

    /**
     * New rank
     */
    private Long newRank;

    /**
     * Previous rank (if available)
     */
    private Long previousRank;

    /**
     * Current score
     */
    private Long score;

    /**
     * Leaderboard scope
     */
    private LeaderboardScope scope;

    /**
     * Time window
     */
    private TimeWindow period;

    /**
     * Region (for regional updates)
     */
    private String region;

    /**
     * Timestamp of the update
     */
    private Instant timestamp;

    public enum NotificationType {
        /**
         * Player entered the top N
         */
        ENTERED_TOP_N,

        /**
         * Player's rank changed within top N
         */
        RANK_CHANGED,

        /**
         * Player dropped out of top N
         */
        EXITED_TOP_N,

        /**
         * New high score
         */
        NEW_HIGH_SCORE,

        /**
         * Leaderboard refresh (periodic update)
         */
        LEADERBOARD_REFRESH
    }

    /**
     * Create a rank change notification
     */
    public static RankUpdateNotification rankChanged(String playerId, Long newRank,
            Long previousRank, Long score, LeaderboardScope scope, TimeWindow period) {
        NotificationType type;
        if (previousRank == null) {
            type = NotificationType.ENTERED_TOP_N;
        } else if (newRank < previousRank) {
            type = NotificationType.RANK_CHANGED;
        } else {
            type = NotificationType.RANK_CHANGED;
        }

        return RankUpdateNotification.builder()
            .type(type)
            .playerId(playerId)
            .newRank(newRank)
            .previousRank(previousRank)
            .score(score)
            .scope(scope)
            .period(period)
            .timestamp(Instant.now())
            .build();
    }
}
