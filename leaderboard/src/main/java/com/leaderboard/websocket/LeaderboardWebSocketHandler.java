package com.leaderboard.websocket;

import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.SendTo;
import org.springframework.messaging.simp.annotation.SubscribeMapping;
import org.springframework.stereotype.Controller;

import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardResponse;
import com.leaderboard.service.LeaderboardService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * WebSocket controller for leaderboard real-time updates.
 */
@Slf4j
@Controller
@RequiredArgsConstructor
public class LeaderboardWebSocketHandler {

    private final LeaderboardService leaderboardService;

    /**
     * Handle subscription to global leaderboard updates.
     * Returns the current top 10 immediately upon subscription.
     */
    @SubscribeMapping("/leaderboard/global/{period}")
    public LeaderboardResponse subscribeToGlobalLeaderboard(
            @DestinationVariable String period) {

        log.debug("New subscription to global/{} leaderboard", period);

        TimeWindow timeWindow = parseTimeWindow(period);
        return leaderboardService.getTopN(LeaderboardScope.GLOBAL, timeWindow, null, 10);
    }

    /**
     * Handle subscription to regional leaderboard updates.
     */
    @SubscribeMapping("/leaderboard/regional/{region}/{period}")
    public LeaderboardResponse subscribeToRegionalLeaderboard(
            @DestinationVariable String region,
            @DestinationVariable String period) {

        log.debug("New subscription to regional/{}/{} leaderboard", region, period);

        TimeWindow timeWindow = parseTimeWindow(period);
        return leaderboardService.getTopN(LeaderboardScope.REGIONAL, timeWindow, region, 10);
    }

    /**
     * Request a leaderboard refresh.
     */
    @MessageMapping("/leaderboard/refresh")
    @SendTo("/topic/leaderboard/refresh")
    public LeaderboardResponse refreshLeaderboard(LeaderboardRefreshRequest request) {
        log.debug("Refresh requested for scope={}, period={}",
            request.scope(), request.period());

        return leaderboardService.getTopN(
            request.scope(),
            request.period(),
            request.region(),
            10
        );
    }

    private TimeWindow parseTimeWindow(String period) {
        try {
            return TimeWindow.valueOf(period.toUpperCase());
        } catch (IllegalArgumentException e) {
            log.warn("Invalid time window: {}, defaulting to DAILY", period);
            return TimeWindow.DAILY;
        }
    }

    /**
     * Request DTO for leaderboard refresh.
     */
    public record LeaderboardRefreshRequest(
        LeaderboardScope scope,
        TimeWindow period,
        String region
    ) {}
}
