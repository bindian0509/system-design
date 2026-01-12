package com.leaderboard.domain;

import java.time.Instant;
import java.util.HashSet;
import java.util.Set;

import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Player entity for storing player profiles.
 */
@Entity
@Table(name = "players", indexes = {
    @Index(name = "idx_player_region", columnList = "region"),
    @Index(name = "idx_player_created", columnList = "createdAt")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Player {

    @Id
    @Column(length = 64)
    private String playerId;

    @Column(nullable = false, length = 100)
    private String displayName;

    @Column(length = 500)
    private String avatarUrl;

    @Column(length = 20)
    private String region;

    /**
     * Friend IDs for friend circle leaderboards
     */
    @ElementCollection(fetch = FetchType.LAZY)
    @Builder.Default
    private Set<String> friendIds = new HashSet<>();

    @Column(nullable = false)
    private Instant createdAt;

    @Column
    private Instant lastActiveAt;

    /**
     * All-time high score
     */
    @Builder.Default
    private Long allTimeHighScore = 0L;

    /**
     * Total games played
     */
    @Builder.Default
    private Long totalGamesPlayed = 0L;
}
