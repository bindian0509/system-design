package com.leaderboard.domain;

/**
 * Defines the scope/context for a leaderboard.
 */
public enum LeaderboardScope {
    /**
     * Global leaderboard across all players
     */
    GLOBAL,

    /**
     * Regional leaderboard for specific geographic regions
     */
    REGIONAL,

    /**
     * Friend circle leaderboard for social connections
     */
    FRIENDS
}
