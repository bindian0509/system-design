package com.urlshortener.controller;

import com.urlshortener.domain.dto.AnalyticsSummary;
import com.urlshortener.service.AnalyticsService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Analytics API endpoints
 */
@RestController
@RequestMapping("/api/v1/analytics")
@RequiredArgsConstructor
public class AnalyticsController {

    private final AnalyticsService analyticsService;

    /**
     * Get analytics summary for a URL
     */
    @GetMapping("/{code}")
    public ResponseEntity<AnalyticsSummary> getAnalytics(@PathVariable String code) {
        AnalyticsSummary summary = analyticsService.getSummary(code);
        return ResponseEntity.ok(summary);
    }

    /**
     * Get real-time click count (last 5 minutes)
     */
    @GetMapping("/{code}/realtime")
    public ResponseEntity<Map<String, Object>> getRealtimeClicks(@PathVariable String code) {
        long clicks = analyticsService.getRealtimeClicks(code);
        return ResponseEntity.ok(Map.of(
                "shortCode", code,
                "realtimeClicks", clicks,
                "windowMinutes", 5
        ));
    }
}
