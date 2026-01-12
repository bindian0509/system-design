package com.leaderboard.service;

import java.time.Instant;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.leaderboard.domain.Player;
import com.leaderboard.repository.PlayerRepository;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Service for player management operations.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PlayerService {

    private final PlayerRepository playerRepository;

    /**
     * Get or create a player.
     */
    @Transactional
    public Player getOrCreatePlayer(String playerId, String displayName, String region) {
        return playerRepository.findByPlayerId(playerId)
            .orElseGet(() -> createPlayer(playerId, displayName, region));
    }

    /**
     * Create a new player.
     */
    @Transactional
    public Player createPlayer(String playerId, String displayName, String region) {
        Player player = Player.builder()
            .playerId(playerId)
            .displayName(displayName != null ? displayName : "Player " + playerId)
            .region(region)
            .createdAt(Instant.now())
            .lastActiveAt(Instant.now())
            .allTimeHighScore(0L)
            .totalGamesPlayed(0L)
            .build();

        player = playerRepository.save(player);
        log.info("Created new player: {}", playerId);

        return player;
    }

    /**
     * Update player's last active time.
     */
    @Transactional
    public void updateLastActive(String playerId) {
        playerRepository.findByPlayerId(playerId).ifPresent(player -> {
            player.setLastActiveAt(Instant.now());
            playerRepository.save(player);
        });
    }

    /**
     * Update player profile.
     */
    @Transactional
    public Player updateProfile(String playerId, String displayName, String avatarUrl) {
        Player player = playerRepository.findByPlayerId(playerId)
            .orElseThrow(() -> new RuntimeException("Player not found: " + playerId));

        if (displayName != null) {
            player.setDisplayName(displayName);
        }
        if (avatarUrl != null) {
            player.setAvatarUrl(avatarUrl);
        }
        player.setLastActiveAt(Instant.now());

        return playerRepository.save(player);
    }

    /**
     * Get player by ID.
     */
    public Optional<Player> getPlayer(String playerId) {
        return playerRepository.findByPlayerId(playerId);
    }

    /**
     * Update all-time high score if current score is higher.
     */
    @Transactional
    public void updateAllTimeHighScore(String playerId, long score) {
        playerRepository.findByPlayerId(playerId).ifPresent(player -> {
            if (score > player.getAllTimeHighScore()) {
                player.setAllTimeHighScore(score);
                playerRepository.save(player);
                log.info("New all-time high score for player {}: {}", playerId, score);
            }
        });
    }

    /**
     * Increment games played counter.
     */
    @Transactional
    public void incrementGamesPlayed(String playerId) {
        playerRepository.findByPlayerId(playerId).ifPresent(player -> {
            player.setTotalGamesPlayed(player.getTotalGamesPlayed() + 1);
            playerRepository.save(player);
        });
    }
}
