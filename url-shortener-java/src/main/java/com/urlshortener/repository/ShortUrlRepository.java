package com.urlshortener.repository;

import com.urlshortener.domain.ShortUrl;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

/**
 * JPA Repository for ShortUrl entity
 * Works with SQLite for local/development and can be swapped with DynamoDB for production
 */
@Repository
public interface ShortUrlRepository extends JpaRepository<ShortUrl, UUID> {

    /**
     * Find URL by short code
     */
    Optional<ShortUrl> findByShortCode(String shortCode);

    /**
     * Check if short code exists
     */
    boolean existsByShortCode(String shortCode);

    /**
     * Find URLs by user ID with pagination
     */
    Page<ShortUrl> findByUserIdOrderByCreatedAtDesc(String userId, Pageable pageable);

    /**
     * Count URLs by user ID
     */
    long countByUserId(String userId);

    /**
     * Find active URLs by user ID
     */
    Page<ShortUrl> findByUserIdAndIsActiveTrueOrderByCreatedAtDesc(String userId, Pageable pageable);

    /**
     * Increment click count atomically
     */
    @Modifying
    @Query("UPDATE ShortUrl u SET u.clickCount = u.clickCount + 1, u.lastAccessedAt = :now WHERE u.shortCode = :code")
    int incrementClickCount(@Param("code") String code, @Param("now") Instant now);

    /**
     * Soft delete by short code
     */
    @Modifying
    @Query("UPDATE ShortUrl u SET u.isActive = false, u.updatedAt = :now WHERE u.shortCode = :code")
    int softDelete(@Param("code") String code, @Param("now") Instant now);

    /**
     * Hard delete by short code (for GDPR)
     */
    void deleteByShortCode(String shortCode);

    /**
     * Hard delete all URLs by user ID (for GDPR erasure)
     */
    void deleteAllByUserId(String userId);

    /**
     * Find expired URLs for cleanup
     */
    @Query("SELECT u FROM ShortUrl u WHERE u.expiresAt IS NOT NULL AND u.expiresAt < :now AND u.isActive = true")
    Page<ShortUrl> findExpiredUrls(@Param("now") Instant now, Pageable pageable);

    /**
     * Find inactive URLs older than specified date (for cleanup)
     */
    @Query("SELECT u FROM ShortUrl u WHERE u.isActive = false AND u.updatedAt < :cutoff")
    Page<ShortUrl> findInactiveUrlsOlderThan(@Param("cutoff") Instant cutoff, Pageable pageable);
}
