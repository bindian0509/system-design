package com.leaderboard.controller;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.leaderboard.domain.HistoricalSnapshot;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardResponse;
import com.leaderboard.service.HistoricalDataService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * REST Controller for historical leaderboard queries.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/leaderboard/history")
@RequiredArgsConstructor
public class HistoricalController {

    private final HistoricalDataService historicalDataService;

    /**
     * Get a specific historical leaderboard snapshot.
     *
     * GET /api/v1/leaderboard/history/{periodId}?scope=GLOBAL&period=DAILY
     *
     * Example: GET /api/v1/leaderboard/history/2026-01-10?scope=GLOBAL&period=DAILY
     */
    @GetMapping("/{periodId}")
    public ResponseEntity<LeaderboardResponse> getHistoricalLeaderboard(
            @PathVariable String periodId,
            @RequestParam(defaultValue = "GLOBAL") LeaderboardScope scope,
            @RequestParam(defaultValue = "DAILY") TimeWindow period,
            @RequestParam(required = false) String region) {

        log.debug("Getting historical leaderboard for periodId={}, scope={}, period={}",
            periodId, scope, period);

        return historicalDataService.getHistoricalLeaderboard(scope, period, periodId, region)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    /**
     * List available historical snapshots.
     *
     * GET /api/v1/leaderboard/history?scope=GLOBAL&period=DAILY&limit=10
     */
    @GetMapping
    public ResponseEntity<List<HistoricalSnapshotSummary>> listSnapshots(
            @RequestParam(defaultValue = "GLOBAL") LeaderboardScope scope,
            @RequestParam(defaultValue = "DAILY") TimeWindow period,
            @RequestParam(required = false) String region,
            @RequestParam(defaultValue = "10") int limit) {

        log.debug("Listing historical snapshots for scope={}, period={}, limit={}",
            scope, period, limit);

        List<HistoricalSnapshot> snapshots = historicalDataService.getRecentSnapshots(
            scope, period, region, Math.min(limit, 100));

        List<HistoricalSnapshotSummary> summaries = snapshots.stream()
            .map(s -> new HistoricalSnapshotSummary(
                s.getPeriodIdentifier(),
                s.getScope(),
                s.getPeriod(),
                s.getRegion(),
                s.getEntryCount(),
                s.getTotalPlayers(),
                s.getCreatedAt()
            ))
            .toList();

        return ResponseEntity.ok(summaries);
    }

    /**
     * Summary DTO for historical snapshots.
     */
    public record HistoricalSnapshotSummary(
        String periodIdentifier,
        LeaderboardScope scope,
        TimeWindow period,
        String region,
        Integer entryCount,
        Long totalPlayers,
        java.time.Instant createdAt
    ) {}
}
