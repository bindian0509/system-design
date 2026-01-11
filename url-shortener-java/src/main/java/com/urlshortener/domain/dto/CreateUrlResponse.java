package com.urlshortener.domain.dto;

import com.urlshortener.domain.ShortUrl;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

/**
 * Response DTO for URL creation
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CreateUrlResponse {

    private UUID id;
    private String shortCode;
    private String shortUrl;
    private String originalUrl;
    private Instant createdAt;
    private Instant expiresAt;

    public static CreateUrlResponse fromEntity(ShortUrl url, String baseUrl) {
        return CreateUrlResponse.builder()
                .id(url.getId())
                .shortCode(url.getShortCode())
                .shortUrl(baseUrl + "/" + url.getShortCode())
                .originalUrl(url.getOriginalUrl())
                .createdAt(url.getCreatedAt())
                .expiresAt(url.getExpiresAt())
                .build();
    }
}
