package com.leaderboard.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import lombok.Data;

@Data
@ConfigurationProperties(prefix = "leaderboard")
public class LeaderboardProperties {

    private String keyPrefix = "lb";
    private int defaultTopLimit = 10;
    private int maxTopLimit = 100;
    private int defaultSurroundingRange = 5;
    private int maxSurroundingRange = 50;

    private Topics topics = new Topics();
    private TimeWindows timeWindows = new TimeWindows();
    private Snapshot snapshot = new Snapshot();
    private Websocket websocket = new Websocket();
    private Notifications notifications = new Notifications();

    @Data
    public static class Topics {
        private String scoreEvents = "score-events";
        private String rankUpdates = "rank-updates";
    }

    @Data
    public static class TimeWindows {
        private int dailyRetentionDays = 7;
        private int weeklyRetentionWeeks = 4;
        private int monthlyRetentionMonths = 12;
    }

    @Data
    public static class Snapshot {
        private boolean enabled = true;
        private String cron = "0 0 * * * *";
    }

    @Data
    public static class Websocket {
        private String endpoint = "/ws/leaderboard";
        private int heartbeatIntervalSeconds = 30;
    }

    @Data
    public static class Notifications {
        private int topNThreshold = 100;
    }
}
