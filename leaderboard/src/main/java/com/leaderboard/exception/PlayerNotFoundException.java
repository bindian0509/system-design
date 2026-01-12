package com.leaderboard.exception;

import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;

/**
 * Exception thrown when a player is not found in a leaderboard.
 */
public class PlayerNotFoundException extends LeaderboardException {

    private final String playerId;
    private final LeaderboardScope scope;
    private final TimeWindow period;

    public PlayerNotFoundException(String playerId, LeaderboardScope scope, TimeWindow period) {
        super(String.format("Player %s not found in %s/%s leaderboard", playerId, scope, period));
        this.playerId = playerId;
        this.scope = scope;
        this.period = period;
    }

    public String getPlayerId() {
        return playerId;
    }

    public LeaderboardScope getScope() {
        return scope;
    }

    public TimeWindow getPeriod() {
        return period;
    }
}
