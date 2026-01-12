package com.leaderboard.domain;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Entity for storing historical leaderboard snapshots.
 */
@Entity
@Table(name = "historical_snapshots", indexes = {
    @Index(name = "idx_snapshot_scope_period", columnList = "scope, period, periodIdentifier"),
    @Index(name = "idx_snapshot_created", columnList = "createdAt")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HistoricalSnapshot {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private LeaderboardScope scope;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private TimeWindow period;

    /**
     * Period identifier (e.g., "2026-01-12" for daily)
     */
    @Column(nullable = false, length = 50)
    private String periodIdentifier;

    /**
     * Region (for regional leaderboards)
     */
    @Column(length = 20)
    private String region;

    /**
     * JSON array of top entries
     */
    @Lob
    @Column(nullable = false, columnDefinition = "TEXT")
    private String entriesJson;

    /**
     * Number of entries in the snapshot
     */
    private Integer entryCount;

    /**
     * Total players when snapshot was taken
     */
    private Long totalPlayers;

    /**
     * When the snapshot was created
     */
    @Column(nullable = false)
    private Instant createdAt;

    /**
     * The end time of the period this snapshot represents
     */
    private Instant periodEndTime;
}
