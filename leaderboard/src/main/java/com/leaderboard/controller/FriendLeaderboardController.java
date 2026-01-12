package com.leaderboard.controller;

import java.util.Set;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.leaderboard.domain.TimeWindow;
import com.leaderboard.domain.dto.LeaderboardResponse;
import com.leaderboard.domain.dto.PlayerRankResponse;
import com.leaderboard.service.FriendLeaderboardService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * REST Controller for friend circle leaderboard operations.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/leaderboard/friends")
@RequiredArgsConstructor
public class FriendLeaderboardController {

    private final FriendLeaderboardService friendLeaderboardService;

    /**
     * Get the leaderboard for a player's friend circle.
     *
     * GET /api/v1/leaderboard/friends/{playerId}?period=DAILY&limit=10
     */
    @GetMapping("/{playerId}")
    public ResponseEntity<LeaderboardResponse> getFriendLeaderboard(
            @PathVariable String playerId,
            @RequestParam(defaultValue = "DAILY") TimeWindow period,
            @RequestParam(defaultValue = "10") int limit) {

        log.debug("Getting friend leaderboard for player: {}", playerId);

        LeaderboardResponse response = friendLeaderboardService.getFriendLeaderboard(
            playerId, period, limit);

        return ResponseEntity.ok(response);
    }

    /**
     * Get a player's rank within their friend circle.
     *
     * GET /api/v1/leaderboard/friends/{playerId}/rank?period=DAILY
     */
    @GetMapping("/{playerId}/rank")
    public ResponseEntity<PlayerRankResponse> getFriendRank(
            @PathVariable String playerId,
            @RequestParam(defaultValue = "DAILY") TimeWindow period) {

        log.debug("Getting friend rank for player: {}", playerId);

        PlayerRankResponse response = friendLeaderboardService.getFriendRank(playerId, period);

        return ResponseEntity.ok(response);
    }

    /**
     * Get a player's friend list.
     *
     * GET /api/v1/leaderboard/friends/{playerId}/list
     */
    @GetMapping("/{playerId}/list")
    public ResponseEntity<FriendListResponse> getFriends(@PathVariable String playerId) {
        log.debug("Getting friend list for player: {}", playerId);

        Set<String> friends = friendLeaderboardService.getFriends(playerId);

        return ResponseEntity.ok(new FriendListResponse(playerId, friends, friends.size()));
    }

    /**
     * Add a friend.
     *
     * POST /api/v1/leaderboard/friends/{playerId}/add/{friendId}
     */
    @PostMapping("/{playerId}/add/{friendId}")
    public ResponseEntity<Void> addFriend(
            @PathVariable String playerId,
            @PathVariable String friendId) {

        log.debug("Adding friend {} for player {}", friendId, playerId);

        friendLeaderboardService.addFriend(playerId, friendId);

        return ResponseEntity.ok().build();
    }

    /**
     * Remove a friend.
     *
     * DELETE /api/v1/leaderboard/friends/{playerId}/remove/{friendId}
     */
    @DeleteMapping("/{playerId}/remove/{friendId}")
    public ResponseEntity<Void> removeFriend(
            @PathVariable String playerId,
            @PathVariable String friendId) {

        log.debug("Removing friend {} for player {}", friendId, playerId);

        friendLeaderboardService.removeFriend(playerId, friendId);

        return ResponseEntity.ok().build();
    }

    /**
     * Response DTO for friend list.
     */
    public record FriendListResponse(
        String playerId,
        Set<String> friendIds,
        int friendCount
    ) {}
}
