package com.leaderboard.repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import com.leaderboard.domain.HistoricalSnapshot;
import com.leaderboard.domain.LeaderboardScope;
import com.leaderboard.domain.TimeWindow;

/**
 * JPA Repository for HistoricalSnapshot entities.
 */
@Repository
public interface HistoricalSnapshotRepository extends JpaRepository<HistoricalSnapshot, Long> {

    /**
     * Find snapshot by scope, period, and period identifier
     */
    Optional<HistoricalSnapshot> findByScopeAndPeriodAndPeriodIdentifierAndRegion(
        LeaderboardScope scope,
        TimeWindow period,
        String periodIdentifier,
        String region
    );

    /**
     * Find latest snapshot for a scope and period
     */
    @Query("SELECT h FROM HistoricalSnapshot h " +
           "WHERE h.scope = :scope AND h.period = :period " +
           "AND (:region IS NULL OR h.region = :region) " +
           "ORDER BY h.createdAt DESC")
    List<HistoricalSnapshot> findLatestByScope(
        @Param("scope") LeaderboardScope scope,
        @Param("period") TimeWindow period,
        @Param("region") String region,
        Pageable pageable
    );

    /**
     * Find snapshots within a date range
     */
    @Query("SELECT h FROM HistoricalSnapshot h " +
           "WHERE h.scope = :scope AND h.period = :period " +
           "AND h.createdAt BETWEEN :startTime AND :endTime " +
           "ORDER BY h.createdAt DESC")
    List<HistoricalSnapshot> findByDateRange(
        @Param("scope") LeaderboardScope scope,
        @Param("period") TimeWindow period,
        @Param("startTime") Instant startTime,
        @Param("endTime") Instant endTime
    );

    /**
     * Delete old snapshots
     */
    void deleteByCreatedAtBefore(Instant cutoffTime);

    /**
     * Count snapshots for a given scope and period
     */
    long countByScopeAndPeriod(LeaderboardScope scope, TimeWindow period);

    /**
     * Check if snapshot exists
     */
    boolean existsByScopeAndPeriodAndPeriodIdentifierAndRegion(
        LeaderboardScope scope,
        TimeWindow period,
        String periodIdentifier,
        String region
    );
}
