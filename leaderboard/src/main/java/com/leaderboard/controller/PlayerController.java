package com.leaderboard.controller;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.leaderboard.domain.Player;
import com.leaderboard.service.PlayerService;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * REST Controller for player management.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/players")
@RequiredArgsConstructor
@Validated
public class PlayerController {

    private final PlayerService playerService;

    /**
     * Get a player by ID.
     *
     * GET /api/v1/players/{playerId}
     */
    @GetMapping("/{playerId}")
    public ResponseEntity<PlayerResponse> getPlayer(@PathVariable String playerId) {
        return playerService.getPlayer(playerId)
            .map(player -> ResponseEntity.ok(toResponse(player)))
            .orElse(ResponseEntity.notFound().build());
    }

    /**
     * Create a new player.
     *
     * POST /api/v1/players
     */
    @PostMapping
    public ResponseEntity<PlayerResponse> createPlayer(@Valid @RequestBody CreatePlayerRequest request) {
        log.debug("Creating player: {}", request.playerId());

        Player player = playerService.createPlayer(
            request.playerId(),
            request.displayName(),
            request.region()
        );

        return ResponseEntity.status(HttpStatus.CREATED).body(toResponse(player));
    }

    /**
     * Update a player's profile.
     *
     * PUT /api/v1/players/{playerId}
     */
    @PutMapping("/{playerId}")
    public ResponseEntity<PlayerResponse> updatePlayer(
            @PathVariable String playerId,
            @Valid @RequestBody UpdatePlayerRequest request) {

        log.debug("Updating player: {}", playerId);

        Player player = playerService.updateProfile(
            playerId,
            request.displayName(),
            request.avatarUrl()
        );

        return ResponseEntity.ok(toResponse(player));
    }

    private PlayerResponse toResponse(Player player) {
        return new PlayerResponse(
            player.getPlayerId(),
            player.getDisplayName(),
            player.getAvatarUrl(),
            player.getRegion(),
            player.getAllTimeHighScore(),
            player.getTotalGamesPlayed(),
            player.getCreatedAt(),
            player.getLastActiveAt()
        );
    }

    // Request/Response DTOs
    public record CreatePlayerRequest(
        @NotBlank String playerId,
        String displayName,
        String region
    ) {}

    public record UpdatePlayerRequest(
        String displayName,
        String avatarUrl
    ) {}

    public record PlayerResponse(
        String playerId,
        String displayName,
        String avatarUrl,
        String region,
        Long allTimeHighScore,
        Long totalGamesPlayed,
        java.time.Instant createdAt,
        java.time.Instant lastActiveAt
    ) {}
}
