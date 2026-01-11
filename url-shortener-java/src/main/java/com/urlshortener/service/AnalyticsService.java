package com.urlshortener.service;

import com.urlshortener.domain.ClickEvent;
import com.urlshortener.domain.dto.AnalyticsSummary;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * Analytics service for tracking and reporting click events
 * In production, this would use Kinesis + Timestream/ClickHouse
 */
@Slf4j
@Service
public class AnalyticsService {

    // In-memory storage for development
    private final Map<String, List<ClickEvent>> eventsByCode = new ConcurrentHashMap<>();

    /**
     * Record a click event (async)
     */
    @Async
    public void recordClick(ClickEvent event) {
        eventsByCode
                .computeIfAbsent(event.getShortCode(), k -> Collections.synchronizedList(new ArrayList<>()))
                .add(event);

        log.debug("Recorded click for {}: device={}, country={}",
                event.getShortCode(), event.getDeviceType(), event.getCountryCode());
    }

    /**
     * Get analytics summary for a URL
     */
    public AnalyticsSummary getSummary(String shortCode) {
        List<ClickEvent> events = eventsByCode.getOrDefault(shortCode, List.of());

        Instant now = Instant.now();
        Instant todayStart = now.truncatedTo(ChronoUnit.DAYS);
        Instant weekAgo = now.minus(7, ChronoUnit.DAYS);
        Instant monthAgo = now.minus(30, ChronoUnit.DAYS);

        long totalClicks = events.size();
        long uniqueVisitors = events.stream()
                .map(ClickEvent::getIpHash)
                .distinct()
                .count();

        long clicksToday = events.stream()
                .filter(e -> e.getTimestamp().isAfter(todayStart))
                .count();

        long clicksThisWeek = events.stream()
                .filter(e -> e.getTimestamp().isAfter(weekAgo))
                .count();

        long clicksThisMonth = events.stream()
                .filter(e -> e.getTimestamp().isAfter(monthAgo))
                .count();

        // Calculate top countries
        Map<String, Long> countryCounts = events.stream()
                .filter(e -> e.getCountryCode() != null)
                .collect(Collectors.groupingBy(ClickEvent::getCountryCode, Collectors.counting()));

        List<AnalyticsSummary.CountryStats> topCountries = countryCounts.entrySet().stream()
                .sorted(Map.Entry.<String, Long>comparingByValue().reversed())
                .limit(10)
                .map(e -> AnalyticsSummary.CountryStats.builder()
                        .countryCode(e.getKey())
                        .countryName(e.getKey()) // Would use lookup in production
                        .clicks(e.getValue())
                        .percentage(totalClicks > 0 ? (e.getValue() * 100.0 / totalClicks) : 0)
                        .build())
                .toList();

        // Calculate top referrers
        Map<String, Long> referrerCounts = events.stream()
                .map(e -> e.getReferrerDomain() != null ? e.getReferrerDomain() : "direct")
                .collect(Collectors.groupingBy(r -> r, Collectors.counting()));

        List<AnalyticsSummary.ReferrerStats> topReferrers = referrerCounts.entrySet().stream()
                .sorted(Map.Entry.<String, Long>comparingByValue().reversed())
                .limit(10)
                .map(e -> AnalyticsSummary.ReferrerStats.builder()
                        .referrer(e.getKey())
                        .clicks(e.getValue())
                        .percentage(totalClicks > 0 ? (e.getValue() * 100.0 / totalClicks) : 0)
                        .build())
                .toList();

        // Calculate device breakdown
        Map<String, Long> deviceCounts = events.stream()
                .map(e -> e.getDeviceType() != null ? e.getDeviceType() : "other")
                .collect(Collectors.groupingBy(d -> d, Collectors.counting()));

        AnalyticsSummary.DeviceBreakdown deviceBreakdown = AnalyticsSummary.DeviceBreakdown.builder()
                .desktop(deviceCounts.getOrDefault("desktop", 0L))
                .mobile(deviceCounts.getOrDefault("mobile", 0L))
                .tablet(deviceCounts.getOrDefault("tablet", 0L))
                .other(deviceCounts.getOrDefault("other", 0L))
                .build();

        return AnalyticsSummary.builder()
                .shortCode(shortCode)
                .totalClicks(totalClicks)
                .uniqueVisitors(uniqueVisitors)
                .clicksToday(clicksToday)
                .clicksThisWeek(clicksThisWeek)
                .clicksThisMonth(clicksThisMonth)
                .topCountries(topCountries)
                .topReferrers(topReferrers)
                .deviceBreakdown(deviceBreakdown)
                .build();
    }

    /**
     * Get real-time clicks (last 5 minutes)
     */
    public long getRealtimeClicks(String shortCode) {
        List<ClickEvent> events = eventsByCode.getOrDefault(shortCode, List.of());
        Instant fiveMinutesAgo = Instant.now().minus(5, ChronoUnit.MINUTES);

        return events.stream()
                .filter(e -> e.getTimestamp().isAfter(fiveMinutesAgo))
                .count();
    }
}
