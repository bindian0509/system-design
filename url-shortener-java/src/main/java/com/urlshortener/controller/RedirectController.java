package com.urlshortener.controller;

import com.urlshortener.domain.ClickEvent;
import com.urlshortener.service.AnalyticsService;
import com.urlshortener.service.UrlService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.codec.digest.DigestUtils;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.time.LocalDate;

/**
 * Controller for handling URL redirects
 */
@Slf4j
@RestController
@RequiredArgsConstructor
public class RedirectController {

    private final UrlService urlService;
    private final AnalyticsService analyticsService;

    /**
     * Handle redirect from short URL to original URL
     */
    @GetMapping("/{code:[a-zA-Z0-9-]+}")
    public ResponseEntity<Void> redirect(
            @PathVariable String code,
            HttpServletRequest request) {

        // Get the redirect URL (throws exception if not found/expired/disabled)
        String originalUrl = urlService.getRedirectUrl(code);

        // Record analytics asynchronously
        recordClickAsync(code, request);

        // Record click count asynchronously
        urlService.recordClick(code);

        log.info("Redirecting {} -> {}", code, originalUrl);

        // Return 308 Permanent Redirect
        return ResponseEntity.status(HttpStatus.PERMANENT_REDIRECT)
                .location(URI.create(originalUrl))
                .header(HttpHeaders.CACHE_CONTROL, "public, max-age=86400")
                .build();
    }

    private void recordClickAsync(String code, HttpServletRequest request) {
        try {
            String clientIp = getClientIp(request);
            String ipHash = hashIpWithDailySalt(clientIp);
            String userAgent = request.getHeader(HttpHeaders.USER_AGENT);
            String referrer = request.getHeader(HttpHeaders.REFERER);

            ClickEvent event = ClickEvent.create(code, ipHash)
                    .withUserAgent(userAgent)
                    .withReferrer(referrer);

            analyticsService.recordClick(event);
        } catch (Exception e) {
            log.warn("Failed to record click event for {}: {}", code, e.getMessage());
        }
    }

    private String getClientIp(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
            return xForwardedFor.split(",")[0].trim();
        }

        String xRealIp = request.getHeader("X-Real-IP");
        if (xRealIp != null && !xRealIp.isEmpty()) {
            return xRealIp;
        }

        return request.getRemoteAddr();
    }

    private String hashIpWithDailySalt(String ip) {
        // Use date as salt for privacy (can't correlate across days)
        String salt = LocalDate.now().toString();
        return DigestUtils.sha256Hex(ip + salt);
    }
}
