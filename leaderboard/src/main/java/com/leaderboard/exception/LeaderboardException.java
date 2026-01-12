package com.leaderboard.exception;

/**
 * Base exception for leaderboard-related errors.
 */
public class LeaderboardException extends RuntimeException {

    public LeaderboardException(String message) {
        super(message);
    }

    public LeaderboardException(String message, Throwable cause) {
        super(message, cause);
    }
}
