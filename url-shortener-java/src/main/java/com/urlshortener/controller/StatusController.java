package com.urlshortener.controller;

import com.urlshortener.config.RegionConfig;
import com.urlshortener.service.GlobalIdGenerator;
import com.urlshortener.service.GlobalIdGenerator.AllocationStatus;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * Status and monitoring endpoints for the ID generator.
 */
@RestController
@RequestMapping("/api/v1/status")
@RequiredArgsConstructor
public class StatusController {

    private final GlobalIdGenerator idGenerator;

    /**
     * Get current ID allocation status.
     */
    @GetMapping("/allocation")
    public ResponseEntity<AllocationStatus> getAllocationStatus() {
        return ResponseEntity.ok(idGenerator.getStatus());
    }

    /**
     * Get global region configuration.
     */
    @GetMapping("/regions")
    public ResponseEntity<List<RegionInfo>> getRegions() {
        List<RegionInfo> regions = Arrays.stream(RegionConfig.values())
            .map(r -> new RegionInfo(
                r.getAwsRegion(),
                r.getShortCode(),
                r.getRangeStart(),
                r.getRangeEnd(),
                r.getCapacity(),
                formatCapacity(r.getCapacity()),
                idGenerator.encode(r.getRangeStart()),
                idGenerator.encode(r.getRangeEnd())
            ))
            .toList();

        return ResponseEntity.ok(regions);
    }

    /**
     * Decode a short code to show its region and numeric value.
     */
    @GetMapping("/decode")
    public ResponseEntity<Map<String, Object>> decodeCode(String code) {
        try {
            long value = idGenerator.decode(code);
            RegionConfig region = idGenerator.getRegionForCode(code);

            return ResponseEntity.ok(Map.of(
                "code", code,
                "numericValue", value,
                "region", region.getAwsRegion(),
                "regionCode", region.getShortCode()
            ));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of(
                "error", e.getMessage()
            ));
        }
    }

    private String formatCapacity(long capacity) {
        if (capacity >= 1_000_000_000_000L) {
            return String.format("%.2f trillion", capacity / 1_000_000_000_000.0);
        } else if (capacity >= 1_000_000_000L) {
            return String.format("%.2f billion", capacity / 1_000_000_000.0);
        }
        return String.format("%,d", capacity);
    }

    public record RegionInfo(
        String awsRegion,
        String shortCode,
        long rangeStart,
        long rangeEnd,
        long capacity,
        String capacityFormatted,
        String firstCode,
        String lastCode
    ) {}
}
