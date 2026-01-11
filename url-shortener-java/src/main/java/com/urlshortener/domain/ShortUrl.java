package com.urlshortener.domain;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Core domain entity representing a shortened URL
 */
@Entity
@Table(name = "urls", indexes = {
    @Index(name = "idx_short_code", columnList = "shortCode", unique = true),
    @Index(name = "idx_user_id", columnList = "userId"),
    @Index(name = "idx_created_at", columnList = "createdAt")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ShortUrl {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false, unique = true, length = 50)
    private String shortCode;

    @Column(nullable = false, length = 4096)
    private String originalUrl;

    @Column(length = 255)
    private String userId;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(nullable = false)
    private Instant updatedAt;

    @Column
    private Instant expiresAt;

    @Column
    private Instant lastAccessedAt;

    @Column(nullable = false)
    @Builder.Default
    private Long clickCount = 0L;

    @Column(nullable = false)
    @Builder.Default
    private Boolean isActive = true;

    @Column(nullable = false)
    @Builder.Default
    private Boolean isCustomAlias = false;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    @Builder.Default
    private UserTier tier = UserTier.FREE;

    @Column(length = 500)
    private String title;

    @Column(length = 2000)
    private String description;

    @ElementCollection(fetch = FetchType.LAZY)
    @CollectionTable(name = "url_tags", joinColumns = @JoinColumn(name = "url_id"))
    @Column(name = "tag")
    @Builder.Default
    private List<String> tags = new ArrayList<>();

    @Column(columnDefinition = "TEXT")
    private String metadata;

    // Business logic methods

    /**
     * Check if the URL has expired
     */
    public boolean isExpired() {
        return expiresAt != null && Instant.now().isAfter(expiresAt);
    }

    /**
     * Check if the URL can be accessed for redirect
     */
    public boolean canRedirect() {
        return isActive && !isExpired();
    }

    /**
     * Record a click on this URL
     */
    public void recordClick() {
        this.clickCount++;
        this.lastAccessedAt = Instant.now();
    }

    /**
     * Soft delete this URL
     */
    public void softDelete() {
        this.isActive = false;
        this.updatedAt = Instant.now();
    }

    /**
     * Create a new ShortUrl with required fields
     */
    public static ShortUrl create(String shortCode, String originalUrl, String userId, UserTier tier, boolean isCustomAlias) {
        return ShortUrl.builder()
                .shortCode(shortCode)
                .originalUrl(originalUrl)
                .userId(userId)
                .tier(tier)
                .isCustomAlias(isCustomAlias)
                .clickCount(0L)
                .isActive(true)
                .build();
    }
}
