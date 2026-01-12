package com.leaderboard.service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.leaderboard.config.LeaderboardProperties;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.Player;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardEntry;
import com.leaderboard.domain.dto.LeaderboardResponse;
import com.leaderboard.domain.dto.PlayerRankResponse;
import com.leaderboard.exception.PlayerNotFoundException;
import com.leaderboard.metrics.LeaderboardMetrics;
import com.leaderboard.repository.PlayerRepository;
import com.leaderboard.repository.RedisLeaderboardRepository;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Service for friend circle leaderboard operations.
 * Aggregates scores from a player's friend list to create personalized leaderboards.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FriendLeaderboardService {

    private final RedisLeaderboardRepository leaderboardRepository;
    private final PlayerRepository playerRepository;
    private final LeaderboardProperties properties;
    private final LeaderboardMetrics metrics;

    /**
     * Get the leaderboard for a player's friend circle.
     * This includes the player and all their friends, ranked by score.
     */
    @CircuitBreaker(name = "redis")
    public LeaderboardResponse getFriendLeaderboard(String playerId, TimeWindow period, int limit) {
        metrics.incrementLeaderboardQueries();

        Instant now = Instant.now();

        // Get the player and their friends
        Player player = playerRepository.findByPlayerId(playerId)
            .orElseThrow(() -> new PlayerNotFoundException(playerId, LeaderboardScope.FRIENDS, period));

        Set<String> friendIds = player.getFriendIds();
        if (friendIds == null || friendIds.isEmpty()) {
            // Return just the player if they have no friends
            return buildSinglePlayerLeaderboard(playerId, period, now);
        }

        // Add the player to the list
        Set<String> allPlayerIds = new java.util.HashSet<>(friendIds);
        allPlayerIds.add(playerId);

        // Get scores for all players from the global leaderboard
        String globalKey = leaderboardRepository.buildKey(
            LeaderboardScope.GLOBAL, period, now, null);

        List<LeaderboardEntry> entries = new ArrayList<>();

        for (String pid : allPlayerIds) {
            Long score = leaderboardRepository.getScore(globalKey, pid);
            if (score != null) {
                entries.add(LeaderboardEntry.builder()
                    .playerId(pid)
                    .score(score)
                    .isRequester(pid.equals(playerId))
                    .build());
            }
        }

        // Sort by score descending and assign ranks
        entries.sort(Comparator.comparingLong(LeaderboardEntry::getScore).reversed());

        long rank = 1;
        for (LeaderboardEntry entry : entries) {
            entry.setRank(rank++);
        }

        // Apply limit
        int effectiveLimit = Math.min(limit, properties.getMaxTopLimit());
        if (entries.size() > effectiveLimit) {
            entries = entries.subList(0, effectiveLimit);
        }

        // Enrich with player profiles
        entries = enrichWithPlayerProfiles(entries);

        return LeaderboardResponse.builder()
            .scope(LeaderboardScope.FRIENDS)
            .period(period)
            .asOf(now)
            .entries(entries)
            .totalPlayers((long) allPlayerIds.size())
            .hasMore(allPlayerIds.size() > effectiveLimit)
            .periodIdentifier(period.getIdentifier(now))
            .build();
    }

    /**
     * Get a player's rank within their friend circle.
     */
    @CircuitBreaker(name = "redis")
    public PlayerRankResponse getFriendRank(String playerId, TimeWindow period) {
        metrics.incrementLeaderboardQueries();

        Instant now = Instant.now();

        // Get the player and their friends
        Player player = playerRepository.findByPlayerId(playerId)
            .orElseThrow(() -> new PlayerNotFoundException(playerId, LeaderboardScope.FRIENDS, period));

        Set<String> friendIds = player.getFriendIds();
        Set<String> allPlayerIds = new java.util.HashSet<>();
        if (friendIds != null) {
            allPlayerIds.addAll(friendIds);
        }
        allPlayerIds.add(playerId);

        // Get scores for all players
        String globalKey = leaderboardRepository.buildKey(
            LeaderboardScope.GLOBAL, period, now, null);

        Long playerScore = leaderboardRepository.getScore(globalKey, playerId);
        if (playerScore == null) {
            throw new PlayerNotFoundException(playerId, LeaderboardScope.FRIENDS, period);
        }

        // Count how many friends have a higher score
        long higherScoreCount = 0;
        for (String friendId : friendIds) {
            Long friendScore = leaderboardRepository.getScore(globalKey, friendId);
            if (friendScore != null && friendScore > playerScore) {
                higherScoreCount++;
            }
        }

        long rank = higherScoreCount + 1;
        long totalPlayers = allPlayerIds.size();
        double percentile = PlayerRankResponse.calculatePercentile(rank, totalPlayers);

        return PlayerRankResponse.builder()
            .playerId(playerId)
            .playerName(player.getDisplayName())
            .rank(rank)
            .score(playerScore)
            .percentile(percentile)
            .totalPlayers(totalPlayers)
            .scope(LeaderboardScope.FRIENDS)
            .period(period)
            .asOf(now)
            .build();
    }

    /**
     * Add a friend relationship.
     */
    public void addFriend(String playerId, String friendId) {
        Player player = playerRepository.findByPlayerId(playerId)
            .orElseThrow(() -> new PlayerNotFoundException(playerId, LeaderboardScope.FRIENDS, TimeWindow.DAILY));

        player.getFriendIds().add(friendId);
        playerRepository.save(player);

        log.info("Added friend {} for player {}", friendId, playerId);
    }

    /**
     * Remove a friend relationship.
     */
    public void removeFriend(String playerId, String friendId) {
        Player player = playerRepository.findByPlayerId(playerId)
            .orElseThrow(() -> new PlayerNotFoundException(playerId, LeaderboardScope.FRIENDS, TimeWindow.DAILY));

        player.getFriendIds().remove(friendId);
        playerRepository.save(player);

        log.info("Removed friend {} for player {}", friendId, playerId);
    }

    /**
     * Get a player's friend list.
     */
    public Set<String> getFriends(String playerId) {
        return playerRepository.findFriendIdsByPlayerId(playerId);
    }

    private LeaderboardResponse buildSinglePlayerLeaderboard(String playerId,
            TimeWindow period, Instant timestamp) {

        String globalKey = leaderboardRepository.buildKey(
            LeaderboardScope.GLOBAL, period, timestamp, null);

        Long score = leaderboardRepository.getScore(globalKey, playerId);

        List<LeaderboardEntry> entries;
        if (score != null) {
            LeaderboardEntry entry = LeaderboardEntry.builder()
                .rank(1L)
                .playerId(playerId)
                .score(score)
                .isRequester(true)
                .build();
            entries = enrichWithPlayerProfiles(List.of(entry));
        } else {
            entries = Collections.emptyList();
        }

        return LeaderboardResponse.builder()
            .scope(LeaderboardScope.FRIENDS)
            .period(period)
            .asOf(timestamp)
            .entries(entries)
            .totalPlayers(1L)
            .hasMore(false)
            .periodIdentifier(period.getIdentifier(timestamp))
            .build();
    }

    private List<LeaderboardEntry> enrichWithPlayerProfiles(List<LeaderboardEntry> entries) {
        if (entries.isEmpty()) {
            return entries;
        }

        Set<String> playerIds = entries.stream()
            .map(LeaderboardEntry::getPlayerId)
            .collect(Collectors.toSet());

        List<Player> players = playerRepository.findByPlayerIdIn(playerIds);
        Map<String, Player> playerMap = players.stream()
            .collect(Collectors.toMap(Player::getPlayerId, Function.identity()));

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
}
