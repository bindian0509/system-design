package com.leaderboard.repository;

import java.util.List;
import java.util.Optional;
import java.util.Set;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import com.leaderboard.domain.Player;

/**
 * JPA Repository for Player entities.
 */
@Repository
public interface PlayerRepository extends JpaRepository<Player, String> {

    /**
     * Find player by ID
     */
    Optional<Player> findByPlayerId(String playerId);

    /**
     * Find multiple players by their IDs
     */
    List<Player> findByPlayerIdIn(Set<String> playerIds);

    /**
     * Find players by region
     */
    List<Player> findByRegion(String region);

    /**
     * Get friend IDs for a player
     */
    @Query("SELECT p.friendIds FROM Player p WHERE p.playerId = :playerId")
    Set<String> findFriendIdsByPlayerId(@Param("playerId") String playerId);

    /**
     * Check if a player exists
     */
    boolean existsByPlayerId(String playerId);

    /**
     * Find players by display name (partial match)
     */
    List<Player> findByDisplayNameContainingIgnoreCase(String displayName);
}
