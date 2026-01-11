package com.urlshortener.domain;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

/**
 * Click event for analytics tracking
 * Privacy-preserving: stores hashed IP, not raw IP
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ClickEvent {

    private UUID eventId;
    private String shortCode;
    private Instant timestamp;

    // Privacy-preserving fields
    private String ipHash;
    private String countryCode;
    private String region;
    private String city;

    // Request metadata
    private String referrerDomain;
    private String deviceType;
    private String browser;
    private String os;

    private boolean isBot;

    /**
     * Create a new click event
     */
    public static ClickEvent create(String shortCode, String ipHash) {
        return ClickEvent.builder()
                .eventId(UUID.randomUUID())
                .shortCode(shortCode)
                .timestamp(Instant.now())
                .ipHash(ipHash)
                .isBot(false)
                .build();
    }

    /**
     * Builder method to add referrer
     */
    public ClickEvent withReferrer(String referrer) {
        this.referrerDomain = extractDomain(referrer);
        return this;
    }

    /**
     * Builder method to add user agent info
     */
    public ClickEvent withUserAgent(String userAgent) {
        if (userAgent != null) {
            this.deviceType = detectDeviceType(userAgent);
            this.browser = detectBrowser(userAgent);
            this.os = detectOS(userAgent);
            this.isBot = detectBot(userAgent);
        }
        return this;
    }

    private String extractDomain(String url) {
        if (url == null || url.isEmpty()) {
            return "direct";
        }
        try {
            java.net.URI uri = new java.net.URI(url);
            String host = uri.getHost();
            return host != null ? host : "direct";
        } catch (Exception e) {
            return "unknown";
        }
    }

    private String detectDeviceType(String userAgent) {
        String ua = userAgent.toLowerCase();
        if (ua.contains("mobile") || ua.contains("android") || ua.contains("iphone")) {
            return "mobile";
        } else if (ua.contains("tablet") || ua.contains("ipad")) {
            return "tablet";
        }
        return "desktop";
    }

    private String detectBrowser(String userAgent) {
        String ua = userAgent.toLowerCase();
        if (ua.contains("chrome") && !ua.contains("edg")) return "Chrome";
        if (ua.contains("firefox")) return "Firefox";
        if (ua.contains("safari") && !ua.contains("chrome")) return "Safari";
        if (ua.contains("edg")) return "Edge";
        if (ua.contains("opera") || ua.contains("opr")) return "Opera";
        return "Other";
    }

    private String detectOS(String userAgent) {
        String ua = userAgent.toLowerCase();
        if (ua.contains("windows")) return "Windows";
        if (ua.contains("mac os")) return "macOS";
        if (ua.contains("linux")) return "Linux";
        if (ua.contains("android")) return "Android";
        if (ua.contains("iphone") || ua.contains("ipad")) return "iOS";
        return "Other";
    }

    private boolean detectBot(String userAgent) {
        String ua = userAgent.toLowerCase();
        return ua.contains("bot") || ua.contains("crawler") ||
               ua.contains("spider") || ua.contains("curl") ||
               ua.contains("wget");
    }
}
