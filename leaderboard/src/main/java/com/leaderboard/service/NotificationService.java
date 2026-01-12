package com.leaderboard.service;

import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import com.leaderboard.config.LeaderboardProperties;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.RankUpdateNotification;
import com.leaderboard.metrics.LeaderboardMetrics;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Service for sending real-time notifications via WebSocket.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationService {

    private final SimpMessagingTemplate messagingTemplate;
    private final LeaderboardProperties properties;
    private final LeaderboardMetrics metrics;

    // WebSocket destinations
    private static final String TOPIC_LEADERBOARD_UPDATES = "/topic/leaderboard";
    private static final String TOPIC_PLAYER_UPDATES = "/topic/player/";
    private static final String TOPIC_REGIONAL_UPDATES = "/topic/regional/";

    /**
     * Notify about a rank change.
     */
    public void notifyRankChange(String playerId, long newRank, long score,
            LeaderboardScope scope, TimeWindow period, String region) {

        RankUpdateNotification notification = RankUpdateNotification.builder()
            .type(RankUpdateNotification.NotificationType.RANK_CHANGED)
            .playerId(playerId)
            .newRank(newRank)
            .score(score)
            .scope(scope)
            .period(period)
            .region(region)
            .timestamp(java.time.Instant.now())
            .build();

        // Send to general leaderboard topic
        sendToLeaderboardTopic(notification, scope, period, region);

        // Send to player-specific topic
        sendToPlayerTopic(playerId, notification);

        metrics.incrementNotificationsSent();

        log.debug("Sent rank update notification for player: {} - rank: {}", playerId, newRank);
    }

    /**
     * Notify when a player enters the top N.
     */
    public void notifyEnteredTopN(String playerId, long rank, long score,
            LeaderboardScope scope, TimeWindow period, String region) {

        RankUpdateNotification notification = RankUpdateNotification.builder()
            .type(RankUpdateNotification.NotificationType.ENTERED_TOP_N)
            .playerId(playerId)
            .newRank(rank)
            .score(score)
            .scope(scope)
            .period(period)
            .region(region)
            .timestamp(java.time.Instant.now())
            .build();

        sendToLeaderboardTopic(notification, scope, period, region);
        sendToPlayerTopic(playerId, notification);

        metrics.incrementNotificationsSent();

        log.info("Player {} entered top {} with rank {}", playerId,
            properties.getNotifications().getTopNThreshold(), rank);
    }

    /**
     * Notify when a player exits the top N.
     */
    public void notifyExitedTopN(String playerId, long previousRank,
            LeaderboardScope scope, TimeWindow period, String region) {

        RankUpdateNotification notification = RankUpdateNotification.builder()
            .type(RankUpdateNotification.NotificationType.EXITED_TOP_N)
            .playerId(playerId)
            .previousRank(previousRank)
            .scope(scope)
            .period(period)
            .region(region)
            .timestamp(java.time.Instant.now())
            .build();

        sendToPlayerTopic(playerId, notification);

        metrics.incrementNotificationsSent();
    }

    /**
     * Broadcast a leaderboard refresh notification.
     */
    public void notifyLeaderboardRefresh(LeaderboardScope scope, TimeWindow period, String region) {
        RankUpdateNotification notification = RankUpdateNotification.builder()
            .type(RankUpdateNotification.NotificationType.LEADERBOARD_REFRESH)
            .scope(scope)
            .period(period)
            .region(region)
            .timestamp(java.time.Instant.now())
            .build();

        sendToLeaderboardTopic(notification, scope, period, region);
    }

    /**
     * Send notification to the main leaderboard topic.
     */
    private void sendToLeaderboardTopic(RankUpdateNotification notification,
            LeaderboardScope scope, TimeWindow period, String region) {

        String destination = buildLeaderboardDestination(scope, period, region);

        try {
            messagingTemplate.convertAndSend(destination, notification);
            log.debug("Sent notification to {}", destination);
        } catch (Exception e) {
            log.error("Failed to send notification to {}", destination, e);
        }
    }

    /**
     * Send notification to a player-specific topic.
     */
    private void sendToPlayerTopic(String playerId, RankUpdateNotification notification) {
        String destination = TOPIC_PLAYER_UPDATES + playerId;

        try {
            messagingTemplate.convertAndSend(destination, notification);
        } catch (Exception e) {
            log.error("Failed to send notification to player {}", playerId, e);
        }
    }

    /**
     * Build the WebSocket destination for a leaderboard.
     */
    private String buildLeaderboardDestination(LeaderboardScope scope, TimeWindow period, String region) {
        StringBuilder dest = new StringBuilder(TOPIC_LEADERBOARD_UPDATES);
        dest.append("/").append(scope.name().toLowerCase());
        dest.append("/").append(period.name().toLowerCase());

        if (region != null && !region.isBlank()) {
            dest.append("/").append(region.toLowerCase());
        }

        return dest.toString();
    }
}
