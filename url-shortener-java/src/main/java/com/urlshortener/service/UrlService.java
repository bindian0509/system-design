package com.urlshortener.service;

import com.urlshortener.domain.ShortUrl;
import com.urlshortener.domain.UserTier;
import com.urlshortener.domain.dto.CreateUrlRequest;
import com.urlshortener.exception.AliasAlreadyExistsException;
import com.urlshortener.exception.InvalidUrlException;
import com.urlshortener.exception.UrlDisabledException;
import com.urlshortener.exception.UrlExpiredException;
import com.urlshortener.exception.UrlNotFoundException;
import com.urlshortener.repository.ShortUrlRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.net.URI;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Optional;

/**
 * Core URL shortening service
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UrlService {

    private static final int MAX_COLLISION_RETRIES = 5;

    private final ShortUrlRepository repository;
    private final CacheService cacheService;
    private final IdGenerator idGenerator;

    @Value("${url-shortener.base-url}")
    private String baseUrl;

    @Value("${url-shortener.url.default-ttl-days:365}")
    private int defaultTtlDays;

    @Value("${url-shortener.url.max-url-length:4096}")
    private int maxUrlLength;

    /**
     * Create a new shortened URL
     */
    @Transactional
    public ShortUrl createUrl(CreateUrlRequest request, String userId, UserTier tier) {
        // Validate URL
        validateUrl(request.getUrl());

        // Determine short code
        String shortCode;
        if (request.getCustomAlias() != null) {
            shortCode = createCustomAlias(request.getCustomAlias(), tier);
        } else {
            shortCode = generateUniqueCode();
        }

        // Calculate expiration
        Instant expiresAt = calculateExpiration(request.getTtlSeconds(), tier);

        // Create entity
        ShortUrl shortUrl = ShortUrl.builder()
                .shortCode(shortCode)
                .originalUrl(request.getUrl())
                .userId(userId)
                .tier(tier)
                .isCustomAlias(request.getCustomAlias() != null)
                .expiresAt(expiresAt)
                .title(request.getTitle())
                .description(request.getDescription())
                .tags(request.getTags())
                .clickCount(0L)
                .isActive(true)
                .build();

        // Save to database
        shortUrl = repository.save(shortUrl);

        // Write-through cache
        cacheService.setUrl(shortCode, request.getUrl());

        log.info("Created short URL: {} -> {} for user: {}",
                shortCode, request.getUrl(), userId);

        return shortUrl;
    }

    /**
     * Get the redirect URL for a short code
     */
    public String getRedirectUrl(String code) {
        // Try cache first
        Optional<String> cached = cacheService.getUrl(code);
        if (cached.isPresent()) {
            return cached.get();
        }

        // Fallback to database
        ShortUrl url = repository.findByShortCode(code)
                .orElseThrow(() -> new UrlNotFoundException(code));

        // Check if URL can be accessed
        if (!url.getIsActive()) {
            throw new UrlDisabledException(code);
        }
        if (url.isExpired()) {
            throw new UrlExpiredException(code);
        }

        // Cache for next time
        cacheService.setUrl(code, url.getOriginalUrl());

        return url.getOriginalUrl();
    }

    /**
     * Get URL details by short code
     */
    public ShortUrl getUrl(String code) {
        return repository.findByShortCode(code)
                .orElseThrow(() -> new UrlNotFoundException(code));
    }

    /**
     * Get URLs by user with pagination
     */
    public Page<ShortUrl> getUrlsByUser(String userId, int page, int size) {
        return repository.findByUserIdOrderByCreatedAtDesc(
                userId, PageRequest.of(page, size));
    }

    /**
     * Delete a URL (soft delete)
     */
    @Transactional
    public void deleteUrl(String code, String userId) {
        ShortUrl url = repository.findByShortCode(code)
                .orElseThrow(() -> new UrlNotFoundException(code));

        // Verify ownership
        if (url.getUserId() != null && !url.getUserId().equals(userId)) {
            throw new UrlNotFoundException(code); // Don't reveal it exists
        }

        // Soft delete
        repository.softDelete(code, Instant.now());

        // Invalidate cache
        cacheService.deleteUrl(code);

        log.info("Deleted URL: {} by user: {}", code, userId);
    }

    /**
     * Hard delete for GDPR compliance
     */
    @Transactional
    public void hardDelete(String code) {
        cacheService.deleteUrl(code);
        repository.deleteByShortCode(code);
        log.info("Hard deleted URL: {} (GDPR)", code);
    }

    /**
     * Record a click (async)
     */
    @Async
    @Transactional
    public void recordClick(String code) {
        try {
            repository.incrementClickCount(code, Instant.now());
        } catch (Exception e) {
            log.warn("Failed to record click for {}: {}", code, e.getMessage());
        }
    }

    /**
     * Check if a code exists
     */
    public boolean codeExists(String code) {
        return repository.existsByShortCode(code);
    }

    /**
     * Get base URL
     */
    public String getBaseUrl() {
        return baseUrl;
    }

    // Private helper methods

    private void validateUrl(String url) {
        if (url == null || url.isBlank()) {
            throw new InvalidUrlException("URL cannot be empty");
        }
        if (url.length() > maxUrlLength) {
            throw new InvalidUrlException("URL exceeds maximum length of " + maxUrlLength);
        }

        try {
            URI uri = new URI(url);
            String scheme = uri.getScheme();
            if (scheme == null || (!scheme.equals("http") && !scheme.equals("https"))) {
                throw new InvalidUrlException("URL must use http or https protocol");
            }
            if (uri.getHost() == null) {
                throw new InvalidUrlException("Invalid URL: missing host");
            }
        } catch (Exception e) {
            throw new InvalidUrlException("Invalid URL format: " + e.getMessage());
        }
    }

    private String createCustomAlias(String alias, UserTier tier) {
        // Validate alias format
        if (!idGenerator.isValidCustomAlias(alias, tier.getMaxAliasLength())) {
            throw new InvalidUrlException(
                    "Invalid alias format. Must be 4-" + tier.getMaxAliasLength() +
                    " alphanumeric characters or hyphens.");
        }

        // Check if already taken
        if (repository.existsByShortCode(alias)) {
            throw new AliasAlreadyExistsException(alias);
        }

        return alias;
    }

    private String generateUniqueCode() {
        for (int i = 0; i < MAX_COLLISION_RETRIES; i++) {
            String code = idGenerator.generate();
            if (!repository.existsByShortCode(code)) {
                return code;
            }
            log.warn("Collision detected for code: {}, attempt: {}", code, i + 1);
        }

        // Fallback to random code
        for (int i = 0; i < MAX_COLLISION_RETRIES; i++) {
            String code = idGenerator.generateRandom();
            if (!repository.existsByShortCode(code)) {
                return code;
            }
        }

        throw new RuntimeException("Failed to generate unique code after " +
                (MAX_COLLISION_RETRIES * 2) + " attempts");
    }

    private Instant calculateExpiration(Long requestedTtlSeconds, UserTier tier) {
        // Use tier default if not specified
        Integer tierDefaultDays = tier.getDefaultTtlDays();

        if (requestedTtlSeconds != null && requestedTtlSeconds > 0) {
            return Instant.now().plusSeconds(requestedTtlSeconds);
        } else if (tierDefaultDays != null) {
            return Instant.now().plus(tierDefaultDays, ChronoUnit.DAYS);
        }

        // No expiration for premium/enterprise
        return null;
    }
}
