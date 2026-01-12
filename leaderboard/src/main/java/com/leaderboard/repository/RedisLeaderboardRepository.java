package com.leaderboard.repository;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.TimeUnit;

import org.springframework.data.redis.core.DefaultTypedTuple;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Repository;

import com.leaderboard.config.LeaderboardProperties;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.ScoreEvent;
import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardEntry;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Repository for leaderboard operations using Redis Sorted Sets.
 * Provides O(log N) operations for all ranking needs.
 */
@Slf4j
@Repository
@RequiredArgsConstructor
public class RedisLeaderboardRepository {

    private final StringRedisTemplate redisTemplate;
    private final LeaderboardProperties properties;

    /**
     * Lua script for atomic score update and rank retrieval.
     * Returns: [newScore, newRank, totalPlayers]
     */
    private static final String UPDATE_SCORE_AND_GET_RANK_SCRIPT = """
        local key = KEYS[1]
        local playerId = ARGV[1]
        local score = tonumber(ARGV[2])
        local mode = ARGV[3]
        local ttl = tonumber(ARGV[4])

        local currentScore = redis.call('ZSCORE', key, playerId)
        local newScore = score

        if mode == 'INCREMENT' then
            if currentScore then
                newScore = tonumber(currentScore) + score
            end
        elseif mode == 'MAX' then
            if currentScore and tonumber(currentScore) >= score then
                newScore = tonumber(currentScore)
            end
        end

        redis.call('ZADD', key, newScore, playerId)

        if ttl > 0 then
            redis.call('EXPIRE', key, ttl)
        end

        local rank = redis.call('ZREVRANK', key, playerId)
        local total = redis.call('ZCARD', key)

        return {tostring(newScore), tostring(rank), tostring(total)}
        """;

    /**
     * Build the Redis key for a leaderboard.
     */
    public String buildKey(LeaderboardScope scope, TimeWindow period, Instant timestamp, String region) {
        String periodId = period.getIdentifier(timestamp);

        return switch (scope) {
            case GLOBAL -> String.format("%s:global:%s:%s",
                properties.getKeyPrefix(), period.name().toLowerCase(), periodId);
            case REGIONAL -> String.format("%s:regional:%s:%s:%s",
                properties.getKeyPrefix(), region, period.name().toLowerCase(), periodId);
            case FRIENDS -> String.format("%s:friends:%s:%s:%s",
                properties.getKeyPrefix(), region, period.name().toLowerCase(), periodId);
        };
    }

    /**
     * Update a player's score in the leaderboard.
     * Returns the new score after update.
     */
    public long updateScore(String key, String playerId, long score,
            ScoreEvent.ScoreUpdateMode mode, long ttlSeconds) {

        ZSetOperations<String, String> zSetOps = redisTemplate.opsForZSet();

        switch (mode) {
            case INCREMENT -> {
                Double newScore = zSetOps.incrementScore(key, playerId, score);
                setTtlIfNeeded(key, ttlSeconds);
                return newScore != null ? newScore.longValue() : score;
            }
            case MAX -> {
                Double currentScore = zSetOps.score(key, playerId);
                if (currentScore == null || score > currentScore) {
                    zSetOps.add(key, playerId, score);
                    setTtlIfNeeded(key, ttlSeconds);
                    return score;
                }
                return currentScore.longValue();
            }
            case SET -> {
                zSetOps.add(key, playerId, score);
                setTtlIfNeeded(key, ttlSeconds);
                return score;
            }
            default -> {
                zSetOps.add(key, playerId, score);
                setTtlIfNeeded(key, ttlSeconds);
                return score;
            }
        }
    }

    /**
     * Update score and atomically get the new rank.
     * Returns: [newScore, rank (0-indexed), totalPlayers]
     */
    public ScoreUpdateResult updateScoreAndGetRank(String key, String playerId, long score,
            ScoreEvent.ScoreUpdateMode mode, long ttlSeconds) {

        RedisScript<List> script = RedisScript.of(UPDATE_SCORE_AND_GET_RANK_SCRIPT, List.class);

        @SuppressWarnings("unchecked")
        List<String> result = redisTemplate.execute(script,
            List.of(key),
            playerId,
            String.valueOf(score),
            mode.name(),
            String.valueOf(ttlSeconds));

        if (result != null && result.size() == 3) {
            return new ScoreUpdateResult(
                Long.parseLong(result.get(0)),
                Long.parseLong(result.get(1)) + 1, // Convert to 1-indexed
                Long.parseLong(result.get(2))
            );
        }

        // Fallback to non-atomic operation
        long newScore = updateScore(key, playerId, score, mode, ttlSeconds);
        Long rank = getRank(key, playerId);
        Long total = getTotalPlayers(key);
        return new ScoreUpdateResult(newScore, rank, total);
    }

    /**
     * Get a player's rank (1-indexed, where 1 is the highest score).
     * Returns null if player is not in the leaderboard.
     */
    public Long getRank(String key, String playerId) {
        Long rank = redisTemplate.opsForZSet().reverseRank(key, playerId);
        return rank != null ? rank + 1 : null; // Convert to 1-indexed
    }

    /**
     * Get a player's score.
     */
    public Long getScore(String key, String playerId) {
        Double score = redisTemplate.opsForZSet().score(key, playerId);
        return score != null ? score.longValue() : null;
    }

    /**
     * Get the top N players from the leaderboard.
     */
    public List<LeaderboardEntry> getTopN(String key, int n) {
        Set<ZSetOperations.TypedTuple<String>> results =
            redisTemplate.opsForZSet().reverseRangeWithScores(key, 0, n - 1);

        return convertToEntries(results, 1);
    }

    /**
     * Get players around a specific rank.
     */
    public List<LeaderboardEntry> getSurrounding(String key, String playerId, int range) {
        Long rank = redisTemplate.opsForZSet().reverseRank(key, playerId);
        if (rank == null) {
            return List.of();
        }

        long start = Math.max(0, rank - range);
        long end = rank + range;

        Set<ZSetOperations.TypedTuple<String>> results =
            redisTemplate.opsForZSet().reverseRangeWithScores(key, start, end);

        return convertToEntries(results, start + 1);
    }

    /**
     * Get total number of players in a leaderboard.
     */
    public Long getTotalPlayers(String key) {
        return redisTemplate.opsForZSet().zCard(key);
    }

    /**
     * Get players by rank range (1-indexed).
     */
    public List<LeaderboardEntry> getByRankRange(String key, long startRank, long endRank) {
        Set<ZSetOperations.TypedTuple<String>> results =
            redisTemplate.opsForZSet().reverseRangeWithScores(key, startRank - 1, endRank - 1);

        return convertToEntries(results, startRank);
    }

    /**
     * Remove a player from a leaderboard.
     */
    public void removePlayer(String key, String playerId) {
        redisTemplate.opsForZSet().remove(key, playerId);
    }

    /**
     * Check if a player exists in the leaderboard.
     */
    public boolean exists(String key, String playerId) {
        return redisTemplate.opsForZSet().score(key, playerId) != null;
    }

    /**
     * Get the score and rank of a player.
     */
    public PlayerScoreRank getPlayerScoreAndRank(String key, String playerId) {
        Double score = redisTemplate.opsForZSet().score(key, playerId);
        if (score == null) {
            return null;
        }

        Long rank = redisTemplate.opsForZSet().reverseRank(key, playerId);
        Long total = getTotalPlayers(key);

        return new PlayerScoreRank(
            playerId,
            score.longValue(),
            rank != null ? rank + 1 : null,
            total
        );
    }

    /**
     * Batch add scores for multiple players.
     */
    public void batchAddScores(String key, List<PlayerScore> scores, long ttlSeconds) {
        Set<ZSetOperations.TypedTuple<String>> tuples = new java.util.HashSet<>();

        for (PlayerScore ps : scores) {
            tuples.add(new DefaultTypedTuple<>(ps.playerId(), (double) ps.score()));
        }

        redisTemplate.opsForZSet().add(key, tuples);
        setTtlIfNeeded(key, ttlSeconds);
    }

    /**
     * Delete a leaderboard key.
     */
    public void deleteKey(String key) {
        redisTemplate.delete(key);
    }

    /**
     * Get all keys matching a pattern.
     */
    public Set<String> getKeys(String pattern) {
        return redisTemplate.keys(pattern);
    }

    private void setTtlIfNeeded(String key, long ttlSeconds) {
        if (ttlSeconds > 0) {
            redisTemplate.expire(key, Duration.ofSeconds(ttlSeconds));
        }
    }

    private List<LeaderboardEntry> convertToEntries(
            Set<ZSetOperations.TypedTuple<String>> tuples, long startRank) {

        if (tuples == null || tuples.isEmpty()) {
            return List.of();
        }

        List<LeaderboardEntry> entries = new ArrayList<>();
        long rank = startRank;

        for (ZSetOperations.TypedTuple<String> tuple : tuples) {
            entries.add(LeaderboardEntry.builder()
                .rank(rank++)
                .playerId(tuple.getValue())
                .score(tuple.getScore() != null ? tuple.getScore().longValue() : 0L)
                .build());
        }

        return entries;
    }

    // Record classes for return types
    public record ScoreUpdateResult(long newScore, long rank, long totalPlayers) {}
    public record PlayerScoreRank(String playerId, long score, Long rank, Long totalPlayers) {}
    public record PlayerScore(String playerId, long score) {}
}
