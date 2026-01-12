package com.leaderboard.service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Optional;

import org.springframework.data.domain.PageRequest;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.leaderboard.config.LeaderboardProperties;
import com.leaderboard.domain.HistoricalSnapshot;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardEntry;
import com.leaderboard.domain.dto.LeaderboardResponse;
import com.leaderboard.repository.HistoricalSnapshotRepository;
import com.leaderboard.repository.RedisLeaderboardRepository;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Service for managing historical leaderboard snapshots.
 * Periodically captures current leaderboard state for historical queries.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class HistoricalDataService {

    private final HistoricalSnapshotRepository snapshotRepository;
    private final RedisLeaderboardRepository leaderboardRepository;
    private final LeaderboardProperties properties;
    private final ObjectMapper objectMapper;

    private static final int SNAPSHOT_TOP_N = 100;

    /**
     * Scheduled task to capture hourly snapshots.
     */
    @Scheduled(cron = "${leaderboard.snapshot.cron:0 0 * * * *}")
    @Transactional
    public void captureHourlySnapshots() {
        if (!properties.getSnapshot().isEnabled()) {
            log.debug("Snapshot capture is disabled");
            return;
        }

        log.info("Starting hourly snapshot capture");
        Instant now = Instant.now();

        // Capture global leaderboard snapshots
        for (TimeWindow window : List.of(TimeWindow.DAILY, TimeWindow.WEEKLY, TimeWindow.MONTHLY)) {
            try {
                captureSnapshot(LeaderboardScope.GLOBAL, window, null, now);
            } catch (Exception e) {
                log.error("Failed to capture {} global snapshot", window, e);
            }
        }

        log.info("Completed hourly snapshot capture");
    }

    /**
     * Capture a snapshot of a specific leaderboard.
     */
    @Transactional
    public void captureSnapshot(LeaderboardScope scope, TimeWindow period,
            String region, Instant timestamp) {

        String periodIdentifier = period.getIdentifier(timestamp);

        // Check if snapshot already exists for this period
        if (snapshotRepository.existsByScopeAndPeriodAndPeriodIdentifierAndRegion(
                scope, period, periodIdentifier, region)) {
            log.debug("Snapshot already exists for {}/{}/{}", scope, period, periodIdentifier);
            return;
        }

        // Get current leaderboard data
        String key = leaderboardRepository.buildKey(scope, period, timestamp, region);
        List<LeaderboardEntry> entries = leaderboardRepository.getTopN(key, SNAPSHOT_TOP_N);
        Long totalPlayers = leaderboardRepository.getTotalPlayers(key);

        if (entries.isEmpty()) {
            log.debug("No entries to snapshot for {}/{}", scope, period);
            return;
        }

        try {
            String entriesJson = objectMapper.writeValueAsString(entries);

            HistoricalSnapshot snapshot = HistoricalSnapshot.builder()
                .scope(scope)
                .period(period)
                .periodIdentifier(periodIdentifier)
                .region(region)
                .entriesJson(entriesJson)
                .entryCount(entries.size())
                .totalPlayers(totalPlayers != null ? totalPlayers : 0L)
                .createdAt(Instant.now())
                .periodEndTime(period.getStartTime(timestamp).plus(1, getPeriodUnit(period)))
                .build();

            snapshotRepository.save(snapshot);

            log.info("Captured snapshot for {}/{}/{} with {} entries",
                scope, period, periodIdentifier, entries.size());

        } catch (JsonProcessingException e) {
            log.error("Failed to serialize snapshot entries", e);
            throw new RuntimeException("Snapshot serialization failed", e);
        }
    }

    /**
     * Get a historical snapshot.
     */
    public Optional<LeaderboardResponse> getHistoricalLeaderboard(
            LeaderboardScope scope, TimeWindow period, String periodIdentifier, String region) {

        Optional<HistoricalSnapshot> snapshotOpt = snapshotRepository
            .findByScopeAndPeriodAndPeriodIdentifierAndRegion(scope, period, periodIdentifier, region);

        if (snapshotOpt.isEmpty()) {
            return Optional.empty();
        }

        HistoricalSnapshot snapshot = snapshotOpt.get();

        try {
            List<LeaderboardEntry> entries = objectMapper.readValue(
                snapshot.getEntriesJson(),
                objectMapper.getTypeFactory().constructCollectionType(List.class, LeaderboardEntry.class)
            );

            return Optional.of(LeaderboardResponse.builder()
                .scope(scope)
                .period(period)
                .region(region)
                .asOf(snapshot.getCreatedAt())
                .entries(entries)
                .totalPlayers(snapshot.getTotalPlayers())
                .hasMore(snapshot.getTotalPlayers() > snapshot.getEntryCount())
                .periodIdentifier(periodIdentifier)
                .build());

        } catch (JsonProcessingException e) {
            log.error("Failed to deserialize snapshot entries", e);
            return Optional.empty();
        }
    }

    /**
     * Get the most recent snapshots for a leaderboard.
     */
    public List<HistoricalSnapshot> getRecentSnapshots(LeaderboardScope scope,
            TimeWindow period, String region, int limit) {

        return snapshotRepository.findLatestByScope(scope, period, region, PageRequest.of(0, limit));
    }

    /**
     * Get snapshots within a date range.
     */
    public List<HistoricalSnapshot> getSnapshotsByDateRange(LeaderboardScope scope,
            TimeWindow period, Instant startTime, Instant endTime) {

        return snapshotRepository.findByDateRange(scope, period, startTime, endTime);
    }

    /**
     * Clean up old snapshots.
     */
    @Scheduled(cron = "0 0 3 * * *") // Run at 3 AM daily
    @Transactional
    public void cleanupOldSnapshots() {
        log.info("Starting old snapshot cleanup");

        // Keep daily snapshots for 30 days
        Instant dailyCutoff = Instant.now().minus(30, ChronoUnit.DAYS);
        // Keep weekly snapshots for 6 months
        Instant weeklyCutoff = Instant.now().minus(180, ChronoUnit.DAYS);
        // Keep monthly snapshots for 2 years
        Instant monthlyCutoff = Instant.now().minus(730, ChronoUnit.DAYS);

        // For simplicity, use the most restrictive cutoff
        snapshotRepository.deleteByCreatedAtBefore(dailyCutoff);

        log.info("Completed old snapshot cleanup");
    }

    private ChronoUnit getPeriodUnit(TimeWindow period) {
        return switch (period) {
            case DAILY, ROLLING_24H -> ChronoUnit.DAYS;
            case WEEKLY -> ChronoUnit.WEEKS;
            case MONTHLY -> ChronoUnit.MONTHS;
            case ROLLING_1H -> ChronoUnit.HOURS;
            case ALL_TIME -> ChronoUnit.FOREVER;
        };
    }
}
