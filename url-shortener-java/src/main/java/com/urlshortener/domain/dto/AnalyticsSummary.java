package com.urlshortener.domain.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Analytics summary for a URL
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnalyticsSummary {

    private String shortCode;
    private long totalClicks;
    private long uniqueVisitors;
    private long clicksToday;
    private long clicksThisWeek;
    private long clicksThisMonth;
    private List<CountryStats> topCountries;
    private List<ReferrerStats> topReferrers;
    private DeviceBreakdown deviceBreakdown;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CountryStats {
        private String countryCode;
        private String countryName;
        private long clicks;
        private double percentage;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ReferrerStats {
        private String referrer;
        private long clicks;
        private double percentage;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DeviceBreakdown {
        private long desktop;
        private long mobile;
        private long tablet;
        private long other;
    }
}
