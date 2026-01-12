package com.leaderboard.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardResponse;
import com.leaderboard.domain.dto.PlayerRankResponse;
import com.leaderboard.domain.dto.RelativeLeaderboardResponse;
import com.leaderboard.service.LeaderboardService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * REST Controller for leaderboard query endpoints.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/leaderboard")
@RequiredArgsConstructor
public class LeaderboardController {

    private final LeaderboardService leaderboardService;

    /**
     * Get the top N players from the leaderboard.
     *
     * GET /api/v1/leaderboard/top?scope=GLOBAL&period=DAILY&limit=10
     */
    @GetMapping("/top")
    public ResponseEntity<LeaderboardResponse> getTopPlayers(
            @RequestParam(defaultValue = "GLOBAL") LeaderboardScope scope,
            @RequestParam(defaultValue = "DAILY") TimeWindow period,
            @RequestParam(required = false) String region,
            @RequestParam(defaultValue = "10") int limit) {

        log.debug("Getting top {} players for scope={}, period={}, region={}",
            limit, scope, period, region);

        LeaderboardResponse response = leaderboardService.getTopN(scope, period, region, limit);

        return ResponseEntity.ok(response);
    }

    /**
     * Get a specific player's rank and score.
     *
     * GET /api/v1/leaderboard/rank/{playerId}?scope=GLOBAL&period=DAILY
     */
    @GetMapping("/rank/{playerId}")
    public ResponseEntity<PlayerRankResponse> getPlayerRank(
            @PathVariable String playerId,
            @RequestParam(defaultValue = "GLOBAL") LeaderboardScope scope,
            @RequestParam(defaultValue = "DAILY") TimeWindow period,
            @RequestParam(required = false) String region) {

        log.debug("Getting rank for player={}, scope={}, period={}", playerId, scope, period);

        PlayerRankResponse response = leaderboardService.getPlayerRank(
            playerId, scope, period, region);

        return ResponseEntity.ok(response);
    }

    /**
     * Get players surrounding a specific player (relative leaderboard).
     *
     * GET /api/v1/leaderboard/around/{playerId}?scope=GLOBAL&period=DAILY&range=5
     */
    @GetMapping("/around/{playerId}")
    public ResponseEntity<RelativeLeaderboardResponse> getSurroundingPlayers(
            @PathVariable String playerId,
            @RequestParam(defaultValue = "GLOBAL") LeaderboardScope scope,
            @RequestParam(defaultValue = "DAILY") TimeWindow period,
            @RequestParam(required = false) String region,
            @RequestParam(defaultValue = "5") int range) {

        log.debug("Getting surrounding players for player={}, scope={}, period={}, range={}",
            playerId, scope, period, range);

        RelativeLeaderboardResponse response = leaderboardService.getSurroundingPlayers(
            playerId, scope, period, region, range);

        return ResponseEntity.ok(response);
    }

    /**
     * Get leaderboard entries by rank range.
     *
     * GET /api/v1/leaderboard/range?scope=GLOBAL&period=DAILY&start=1&end=100
     */
    @GetMapping("/range")
    public ResponseEntity<LeaderboardResponse> getByRankRange(
            @RequestParam(defaultValue = "GLOBAL") LeaderboardScope scope,
            @RequestParam(defaultValue = "DAILY") TimeWindow period,
            @RequestParam(required = false) String region,
            @RequestParam long start,
            @RequestParam long end) {

        log.debug("Getting leaderboard range [{}-{}] for scope={}, period={}",
            start, end, scope, period);

        if (start < 1 || end < start) {
            throw new IllegalArgumentException("Invalid rank range: start must be >= 1 and end >= start");
        }

        if (end - start > 100) {
            throw new IllegalArgumentException("Range cannot exceed 100 entries");
        }

        LeaderboardResponse response = leaderboardService.getByRankRange(
            scope, period, region, start, end);

        return ResponseEntity.ok(response);
    }
}
