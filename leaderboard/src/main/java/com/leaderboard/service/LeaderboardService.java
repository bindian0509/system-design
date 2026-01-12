package com.leaderboard.service;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import com.leaderboard.config.CacheConfig;
import com.leaderboard.config.LeaderboardProperties;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.Player;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardEntry;
import com.leaderboard.domain.dto.LeaderboardResponse;
import com.leaderboard.domain.dto.PlayerRankResponse;
import com.leaderboard.domain.dto.RelativeLeaderboardResponse;
import com.leaderboard.exception.PlayerNotFoundException;
import com.leaderboard.metrics.LeaderboardMetrics;
import com.leaderboard.repository.PlayerRepository;
import com.leaderboard.repository.RedisLeaderboardRepository;
import com.leaderboard.repository.RedisLeaderboardRepository.PlayerScoreRank;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Service for querying leaderboard data.
 * Provides top-N, player rank, and surrounding player queries.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LeaderboardService {

    private final RedisLeaderboardRepository leaderboardRepository;
    private final PlayerRepository playerRepository;
    private final LeaderboardProperties properties;
    private final LeaderboardMetrics metrics;

    /**
     * Get the top N players from a leaderboard.
     */
    @CircuitBreaker(name = "redis", fallbackMethod = "getTopNFallback")
    @Cacheable(cacheNames = CacheConfig.LEADERBOARD_TOP_CACHE,
               key = "#scope.name() + ':' + #period.name() + ':' + #region + ':' + #limit")
    public LeaderboardResponse getTopN(LeaderboardScope scope, TimeWindow period,
            String region, int limit) {

        Timer.Sample sample = Timer.start();
        metrics.incrementLeaderboardQueries();

        try {
            // Validate and cap limit
            int effectiveLimit = Math.min(limit, properties.getMaxTopLimit());
            if (effectiveLimit <= 0) {
                effectiveLimit = properties.getDefaultTopLimit();
            }

            Instant now = Instant.now();
            String key = leaderboardRepository.buildKey(scope, period, now, region);

            // Get top entries from Redis
            List<LeaderboardEntry> entries = leaderboardRepository.getTopN(key, effectiveLimit);

            // Enrich with player profiles
            entries = enrichWithPlayerProfiles(entries);

            // Get total players
            Long totalPlayers = leaderboardRepository.getTotalPlayers(key);

            metrics.incrementCacheHits();
            sample.stop(metrics.getLeaderboardQueryTimer());

            return LeaderboardResponse.builder()
                .scope(scope)
                .period(period)
                .region(region)
                .asOf(now)
                .entries(entries)
                .totalPlayers(totalPlayers != null ? totalPlayers : 0L)
                .hasMore(entries.size() >= effectiveLimit && totalPlayers > effectiveLimit)
                .periodIdentifier(period.getIdentifier(now))
                .build();

        } catch (Exception e) {
            sample.stop(metrics.getLeaderboardQueryTimer());
            throw e;
        }
    }

    /**
     * Get a specific player's rank and score.
     */
    @CircuitBreaker(name = "redis", fallbackMethod = "getPlayerRankFallback")
    public PlayerRankResponse getPlayerRank(String playerId, LeaderboardScope scope,
            TimeWindow period, String region) {

        Timer.Sample sample = Timer.start();
        metrics.incrementLeaderboardQueries();

        try {
            Instant now = Instant.now();
            String key = leaderboardRepository.buildKey(scope, period, now, region);

            PlayerScoreRank scoreRank = leaderboardRepository.getPlayerScoreAndRank(key, playerId);

            if (scoreRank == null) {
                throw new PlayerNotFoundException(playerId, scope, period);
            }

            // Calculate percentile
            double percentile = PlayerRankResponse.calculatePercentile(
                scoreRank.rank(), scoreRank.totalPlayers());

            // Get player profile
            Player player = playerRepository.findByPlayerId(playerId).orElse(null);

            sample.stop(metrics.getLeaderboardQueryTimer());

            return PlayerRankResponse.builder()
                .playerId(playerId)
                .playerName(player != null ? player.getDisplayName() : null)
                .rank(scoreRank.rank())
                .score(scoreRank.score())
                .percentile(percentile)
                .totalPlayers(scoreRank.totalPlayers())
                .scope(scope)
                .period(period)
                .region(region)
                .asOf(now)
                .build();

        } catch (PlayerNotFoundException e) {
            sample.stop(metrics.getLeaderboardQueryTimer());
            throw e;
        } catch (Exception e) {
            sample.stop(metrics.getLeaderboardQueryTimer());
            throw e;
        }
    }

    /**
     * Get players surrounding a specific player (relative leaderboard).
     */
    @CircuitBreaker(name = "redis", fallbackMethod = "getSurroundingPlayersFallback")
    public RelativeLeaderboardResponse getSurroundingPlayers(String playerId,
            LeaderboardScope scope, TimeWindow period, String region, int range) {

        Timer.Sample sample = Timer.start();
        metrics.incrementLeaderboardQueries();

        try {
            // Validate and cap range
            int effectiveRange = Math.min(range, properties.getMaxSurroundingRange());
            if (effectiveRange <= 0) {
                effectiveRange = properties.getDefaultSurroundingRange();
            }

            Instant now = Instant.now();
            String key = leaderboardRepository.buildKey(scope, period, now, region);

            // Get player's current rank and score
            PlayerScoreRank playerScoreRank = leaderboardRepository.getPlayerScoreAndRank(key, playerId);

            if (playerScoreRank == null) {
                throw new PlayerNotFoundException(playerId, scope, period);
            }

            // Get surrounding players
            List<LeaderboardEntry> entries = leaderboardRepository.getSurrounding(
                key, playerId, effectiveRange);

            // Mark the requester in the entries
            for (LeaderboardEntry entry : entries) {
                if (entry.getPlayerId().equals(playerId)) {
                    entry.setRequester(true);
                }
            }

            // Enrich with player profiles
            entries = enrichWithPlayerProfiles(entries);

            sample.stop(metrics.getLeaderboardQueryTimer());

            return RelativeLeaderboardResponse.builder()
                .playerId(playerId)
                .playerRank(playerScoreRank.rank())
                .playerScore(playerScoreRank.score())
                .entries(entries)
                .scope(scope)
                .period(period)
                .region(region)
                .asOf(now)
                .totalPlayers(playerScoreRank.totalPlayers())
                .build();

        } catch (PlayerNotFoundException e) {
            sample.stop(metrics.getLeaderboardQueryTimer());
            throw e;
        } catch (Exception e) {
            sample.stop(metrics.getLeaderboardQueryTimer());
            throw e;
        }
    }

    /**
     * Get leaderboard entries by rank range.
     */
    @CircuitBreaker(name = "redis")
    public LeaderboardResponse getByRankRange(LeaderboardScope scope, TimeWindow period,
            String region, long startRank, long endRank) {

        Instant now = Instant.now();
        String key = leaderboardRepository.buildKey(scope, period, now, region);

        List<LeaderboardEntry> entries = leaderboardRepository.getByRankRange(key, startRank, endRank);
        entries = enrichWithPlayerProfiles(entries);

        Long totalPlayers = leaderboardRepository.getTotalPlayers(key);

        return LeaderboardResponse.builder()
            .scope(scope)
            .period(period)
            .region(region)
            .asOf(now)
            .entries(entries)
            .totalPlayers(totalPlayers != null ? totalPlayers : 0L)
            .hasMore(endRank < totalPlayers)
            .periodIdentifier(period.getIdentifier(now))
            .build();
    }

    /**
     * Enrich leaderboard entries with player profile information.
     */
    private List<LeaderboardEntry> enrichWithPlayerProfiles(List<LeaderboardEntry> entries) {
        if (entries.isEmpty()) {
            return entries;
        }

        // Collect player IDs
        Set<String> playerIds = entries.stream()
            .map(LeaderboardEntry::getPlayerId)
            .collect(Collectors.toSet());

        // Batch fetch player profiles
        List<Player> players = playerRepository.findByPlayerIdIn(playerIds);
        Map<String, Player> playerMap = players.stream()
            .collect(Collectors.toMap(Player::getPlayerId, Function.identity()));

        // Enrich entries
        for (LeaderboardEntry entry : entries) {
            Player player = playerMap.get(entry.getPlayerId());
            if (player != null) {
                entry.setPlayerName(player.getDisplayName());
                entry.setAvatarUrl(player.getAvatarUrl());
                entry.setRegion(player.getRegion());
            }
        }

        return entries;
    }

    // Fallback methods
    @SuppressWarnings("unused")
    private LeaderboardResponse getTopNFallback(LeaderboardScope scope, TimeWindow period,
            String region, int limit, Throwable throwable) {

        log.warn("Fallback for getTopN: scope={}, period={}, error={}",
            scope, period, throwable.getMessage());

        metrics.incrementRedisCircuitBreakerOpen();

        return LeaderboardResponse.builder()
            .scope(scope)
            .period(period)
            .region(region)
            .asOf(Instant.now())
            .entries(List.of())
            .totalPlayers(0L)
            .hasMore(false)
            .build();
    }

    @SuppressWarnings("unused")
    private PlayerRankResponse getPlayerRankFallback(String playerId, LeaderboardScope scope,
            TimeWindow period, String region, Throwable throwable) {

        log.warn("Fallback for getPlayerRank: player={}, error={}",
            playerId, throwable.getMessage());

        metrics.incrementRedisCircuitBreakerOpen();

        throw new RuntimeException("Leaderboard temporarily unavailable", throwable);
    }

    @SuppressWarnings("unused")
    private RelativeLeaderboardResponse getSurroundingPlayersFallback(String playerId,
            LeaderboardScope scope, TimeWindow period, String region, int range,
            Throwable throwable) {

        log.warn("Fallback for getSurroundingPlayers: player={}, error={}",
            playerId, throwable.getMessage());

        metrics.incrementRedisCircuitBreakerOpen();

        throw new RuntimeException("Leaderboard temporarily unavailable", throwable);
    }
}
