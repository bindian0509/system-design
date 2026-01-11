package com.urlshortener.controller;

import com.urlshortener.domain.ShortUrl;
import com.urlshortener.domain.UserTier;
import com.urlshortener.domain.dto.CreateUrlRequest;
import com.urlshortener.domain.dto.CreateUrlResponse;
import com.urlshortener.domain.dto.UrlResponse;
import com.urlshortener.security.AuthenticatedUser;
import com.urlshortener.service.UrlService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * REST controller for URL management
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/urls")
@RequiredArgsConstructor
public class UrlController {

    private final UrlService urlService;

    /**
     * Create a new shortened URL
     */
    @PostMapping
    public ResponseEntity<CreateUrlResponse> createUrl(
            @Valid @RequestBody CreateUrlRequest request,
            @AuthenticationPrincipal AuthenticatedUser user) {

        String userId = user != null ? user.getUserId() : null;
        UserTier tier = user != null ? user.getTier() : UserTier.FREE;

        ShortUrl shortUrl = urlService.createUrl(request, userId, tier);
        CreateUrlResponse response = CreateUrlResponse.fromEntity(shortUrl, urlService.getBaseUrl());

        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    /**
     * Get URL details by short code
     */
    @GetMapping("/{code}")
    public ResponseEntity<UrlResponse> getUrl(@PathVariable String code) {
        ShortUrl url = urlService.getUrl(code);
        return ResponseEntity.ok(UrlResponse.fromEntity(url, urlService.getBaseUrl()));
    }

    /**
     * List URLs for authenticated user
     */
    @GetMapping
    public ResponseEntity<PagedResponse<UrlResponse>> listUrls(
            @AuthenticationPrincipal AuthenticatedUser user,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {

        if (user == null) {
            return ResponseEntity.ok(PagedResponse.empty());
        }

        Page<ShortUrl> urls = urlService.getUrlsByUser(user.getUserId(), page, size);

        List<UrlResponse> content = urls.getContent().stream()
                .map(url -> UrlResponse.fromEntity(url, urlService.getBaseUrl()))
                .toList();

        return ResponseEntity.ok(PagedResponse.<UrlResponse>builder()
                .content(content)
                .page(page)
                .size(size)
                .totalElements(urls.getTotalElements())
                .totalPages(urls.getTotalPages())
                .hasNext(urls.hasNext())
                .hasPrevious(urls.hasPrevious())
                .build());
    }

    /**
     * Delete a URL
     */
    @DeleteMapping("/{code}")
    public ResponseEntity<Void> deleteUrl(
            @PathVariable String code,
            @AuthenticationPrincipal AuthenticatedUser user) {

        String userId = user != null ? user.getUserId() : null;
        urlService.deleteUrl(code, userId);

        return ResponseEntity.noContent().build();
    }

    /**
     * Paginated response wrapper
     */
    @lombok.Data
    @lombok.Builder
    @lombok.NoArgsConstructor
    @lombok.AllArgsConstructor
    public static class PagedResponse<T> {
        private List<T> content;
        private int page;
        private int size;
        private long totalElements;
        private int totalPages;
        private boolean hasNext;
        private boolean hasPrevious;

        public static <T> PagedResponse<T> empty() {
            return PagedResponse.<T>builder()
                    .content(List.of())
                    .page(0)
                    .size(0)
                    .totalElements(0)
                    .totalPages(0)
                    .hasNext(false)
                    .hasPrevious(false)
                    .build();
        }
    }
}
