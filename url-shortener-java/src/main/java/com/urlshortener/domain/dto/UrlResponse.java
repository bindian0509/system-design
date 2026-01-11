package com.urlshortener.domain.dto;

import com.urlshortener.domain.ShortUrl;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Full URL details response
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UrlResponse {

    private UUID id;
    private String shortCode;
    private String shortUrl;
    private String originalUrl;
    private Instant createdAt;
    private Instant updatedAt;
    private Instant expiresAt;
    private Long clickCount;
    private Boolean isActive;
    private String title;
    private String description;
    private List<String> tags;

    public static UrlResponse fromEntity(ShortUrl url, String baseUrl) {
        return UrlResponse.builder()
                .id(url.getId())
                .shortCode(url.getShortCode())
                .shortUrl(baseUrl + "/" + url.getShortCode())
                .originalUrl(url.getOriginalUrl())
                .createdAt(url.getCreatedAt())
                .updatedAt(url.getUpdatedAt())
                .expiresAt(url.getExpiresAt())
                .clickCount(url.getClickCount())
                .isActive(url.getIsActive())
                .title(url.getTitle())
                .description(url.getDescription())
                .tags(url.getTags())
                .build();
    }
}
