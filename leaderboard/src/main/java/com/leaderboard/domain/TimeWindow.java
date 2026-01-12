package com.leaderboard.domain;

import java.time.DayOfWeek;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.time.temporal.TemporalAdjusters;
import java.time.temporal.WeekFields;
import java.util.Locale;

/**
 * Defines the time window for leaderboard aggregation.
 */
public enum TimeWindow {
    /**
     * Calendar-based daily leaderboard (resets at midnight UTC)
     */
    DAILY {
        @Override
        public String getIdentifier(Instant timestamp) {
            return LocalDate.ofInstant(timestamp, ZoneOffset.UTC).toString();
        }

        @Override
        public Instant getStartTime(Instant timestamp) {
            return LocalDate.ofInstant(timestamp, ZoneOffset.UTC)
                .atStartOfDay(ZoneOffset.UTC)
                .toInstant();
        }

        @Override
        public long getTtlSeconds() {
            return 7 * 24 * 60 * 60; // 7 days retention
        }
    },

    /**
     * Calendar-based weekly leaderboard (resets on Sunday midnight UTC)
     */
    WEEKLY {
        @Override
        public String getIdentifier(Instant timestamp) {
            LocalDate date = LocalDate.ofInstant(timestamp, ZoneOffset.UTC);
            WeekFields weekFields = WeekFields.of(Locale.US);
            int year = date.getYear();
            int week = date.get(weekFields.weekOfWeekBasedYear());
            return String.format("%d-W%02d", year, week);
        }

        @Override
        public Instant getStartTime(Instant timestamp) {
            return LocalDate.ofInstant(timestamp, ZoneOffset.UTC)
                .with(TemporalAdjusters.previousOrSame(DayOfWeek.SUNDAY))
                .atStartOfDay(ZoneOffset.UTC)
                .toInstant();
        }

        @Override
        public long getTtlSeconds() {
            return 4 * 7 * 24 * 60 * 60; // 4 weeks retention
        }
    },

    /**
     * Calendar-based monthly leaderboard (resets on 1st of month)
     */
    MONTHLY {
        @Override
        public String getIdentifier(Instant timestamp) {
            LocalDate date = LocalDate.ofInstant(timestamp, ZoneOffset.UTC);
            return String.format("%d-%02d", date.getYear(), date.getMonthValue());
        }

        @Override
        public Instant getStartTime(Instant timestamp) {
            return LocalDate.ofInstant(timestamp, ZoneOffset.UTC)
                .withDayOfMonth(1)
                .atStartOfDay(ZoneOffset.UTC)
                .toInstant();
        }

        @Override
        public long getTtlSeconds() {
            return 12 * 30 * 24 * 60 * 60L; // ~12 months retention
        }
    },

    /**
     * Rolling window - last 1 hour
     */
    ROLLING_1H {
        @Override
        public String getIdentifier(Instant timestamp) {
            return "rolling-1h";
        }

        @Override
        public Instant getStartTime(Instant timestamp) {
            return timestamp.minus(1, ChronoUnit.HOURS);
        }

        @Override
        public long getTtlSeconds() {
            return 2 * 60 * 60; // 2 hours
        }
    },

    /**
     * Rolling window - last 24 hours
     */
    ROLLING_24H {
        @Override
        public String getIdentifier(Instant timestamp) {
            return "rolling-24h";
        }

        @Override
        public Instant getStartTime(Instant timestamp) {
            return timestamp.minus(24, ChronoUnit.HOURS);
        }

        @Override
        public long getTtlSeconds() {
            return 48 * 60 * 60; // 48 hours
        }
    },

    /**
     * All-time leaderboard
     */
    ALL_TIME {
        @Override
        public String getIdentifier(Instant timestamp) {
            return "all-time";
        }

        @Override
        public Instant getStartTime(Instant timestamp) {
            return Instant.EPOCH;
        }

        @Override
        public long getTtlSeconds() {
            return -1; // No expiration
        }
    };

    /**
     * Get the identifier string for this time window at the given timestamp.
     * Used for constructing Redis keys.
     */
    public abstract String getIdentifier(Instant timestamp);

    /**
     * Get the start time of this window for the given timestamp.
     */
    public abstract Instant getStartTime(Instant timestamp);

    /**
     * Get the TTL in seconds for leaderboard data in this time window.
     * Returns -1 for no expiration.
     */
    public abstract long getTtlSeconds();
}
