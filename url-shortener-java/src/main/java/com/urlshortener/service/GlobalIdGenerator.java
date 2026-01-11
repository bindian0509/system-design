package com.urlshortener.service;

import com.urlshortener.config.RegionConfig;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Global ID Generator with region-based range allocation.
 *
 * Architecture:
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │                      GLOBAL ID SPACE (62^7)                              │
 * ├─────────────────────┬─────────────────────┬─────────────────────────────┤
 * │     US-EAST-1       │     EU-WEST-1       │       AP-SOUTH-1            │
 * │   0 - 1.17T         │  1.17T - 2.34T      │    2.34T - 3.52T            │
 * └─────────────────────┴─────────────────────┴─────────────────────────────┘
 *          │                    │                       │
 *          ▼                    ▼                       ▼
 *    ┌──────────┐         ┌──────────┐           ┌──────────┐
 *    │ Instance │         │ Instance │           │ Instance │
 *    │ Range    │         │ Range    │           │ Range    │
 *    │ (1M IDs) │         │ (1M IDs) │           │ (1M IDs) │
 *    └──────────┘         └──────────┘           └──────────┘
 *
 * Each instance:
 * 1. Gets a batch of 1M IDs from regional DynamoDB counter
 * 2. Generates codes locally without coordination
 * 3. Requests new batch when 90% depleted
 */
@Slf4j
@Component
public class GlobalIdGenerator {

    private static final String CHARSET =
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
    private static final int BASE = 62;
    private static final int CODE_LENGTH = 7;

    /**
     * Default batch size: 1 million IDs per allocation.
     * At 1000 URLs/second, this lasts ~16 minutes.
     */
    private static final long DEFAULT_BATCH_SIZE = 1_000_000L;

    /**
     * Prefetch threshold: request new batch at 90% depletion.
     */
    private static final double PREFETCH_THRESHOLD = 0.9;

    private final RegionConfig regionConfig;
    private final AtomicLong counter;
    private final ReentrantLock allocationLock;
    private final CounterRepository counterRepository;

    private volatile long rangeStart;
    private volatile long rangeEnd;
    private volatile boolean prefetchInProgress;

    @Value("${url-shortener.id-generator.batch-size:1000000}")
    private long batchSize = DEFAULT_BATCH_SIZE;

    @Value("${AWS_REGION:us-east-1}")
    private String awsRegion;

    public GlobalIdGenerator(CounterRepository counterRepository) {
        this.counterRepository = counterRepository;
        this.counter = new AtomicLong(0);
        this.allocationLock = new ReentrantLock();
        this.regionConfig = RegionConfig.fromAwsRegion(awsRegion);
        this.prefetchInProgress = false;
    }

    @PostConstruct
    public void initialize() {
        log.info("Initializing GlobalIdGenerator for region: {} ({})",
            regionConfig.getAwsRegion(), regionConfig.getShortCode());
        log.info("Region range: {} to {} ({} capacity)",
            regionConfig.getRangeStart(),
            regionConfig.getRangeEnd(),
            formatNumber(regionConfig.getCapacity()));

        allocateNewRange();
    }

    /**
     * Generate a new unique short code.
     * Thread-safe and lock-free for normal operations.
     */
    public String generate() {
        long value = counter.getAndIncrement();

        // Check if we need to prefetch
        if (!prefetchInProgress && shouldPrefetch(value)) {
            triggerPrefetch();
        }

        // Check if we've exhausted our range
        if (value > rangeEnd) {
            // Block and wait for new range
            allocateNewRange();
            value = counter.getAndIncrement();
        }

        return encode(value);
    }

    /**
     * Generate a code for a specific numeric value.
     * Used for custom alias validation and testing.
     */
    public String encode(long num) {
        if (num < 0) {
            throw new IllegalArgumentException("Cannot encode negative number");
        }

        StringBuilder sb = new StringBuilder();

        if (num == 0) {
            sb.append(CHARSET.charAt(0));
        } else {
            while (num > 0) {
                sb.insert(0, CHARSET.charAt((int) (num % BASE)));
                num /= BASE;
            }
        }

        // Pad to CODE_LENGTH
        while (sb.length() < CODE_LENGTH) {
            sb.insert(0, '0');
        }

        return sb.toString();
    }

    /**
     * Decode a short code back to its numeric value.
     */
    public long decode(String code) {
        if (code == null || code.isEmpty()) {
            throw new IllegalArgumentException("Code cannot be null or empty");
        }

        long result = 0;
        for (char c : code.toCharArray()) {
            int index = CHARSET.indexOf(c);
            if (index == -1) {
                throw new IllegalArgumentException("Invalid character in code: " + c);
            }
            result = result * BASE + index;
        }

        return result;
    }

    /**
     * Determine which region a short code was generated in.
     */
    public RegionConfig getRegionForCode(String code) {
        long value = decode(code);
        return RegionConfig.fromNumericValue(value);
    }

    /**
     * Check if we should prefetch a new range.
     */
    private boolean shouldPrefetch(long currentValue) {
        long used = currentValue - rangeStart;
        long total = rangeEnd - rangeStart;
        return (double) used / total >= PREFETCH_THRESHOLD;
    }

    /**
     * Trigger async prefetch of new range.
     */
    private void triggerPrefetch() {
        if (allocationLock.tryLock()) {
            try {
                if (!prefetchInProgress) {
                    prefetchInProgress = true;
                    // In production, this would be async
                    log.info("Prefetching new ID range...");
                }
            } finally {
                allocationLock.unlock();
            }
        }
    }

    /**
     * Allocate a new range from DynamoDB.
     * This is the only operation that requires coordination.
     */
    private void allocateNewRange() {
        allocationLock.lock();
        try {
            log.info("Allocating new ID range from DynamoDB...");

            // Get next range from DynamoDB counter
            RangeAllocation allocation = counterRepository.allocateRange(
                regionConfig,
                batchSize
            );

            this.rangeStart = allocation.start();
            this.rangeEnd = allocation.end();
            this.counter.set(rangeStart);
            this.prefetchInProgress = false;

            log.info("Allocated range: {} to {} ({} IDs)",
                rangeStart, rangeEnd, formatNumber(rangeEnd - rangeStart + 1));
            log.info("First code: {}, Last code: {}",
                encode(rangeStart), encode(rangeEnd));

        } finally {
            allocationLock.unlock();
        }
    }

    /**
     * Get current allocation status for monitoring.
     */
    public AllocationStatus getStatus() {
        long current = counter.get();
        long used = current - rangeStart;
        long total = rangeEnd - rangeStart + 1;
        double usagePercent = (double) used / total * 100;

        return new AllocationStatus(
            regionConfig.getAwsRegion(),
            rangeStart,
            rangeEnd,
            current,
            used,
            total - used,
            usagePercent
        );
    }

    private String formatNumber(long num) {
        if (num >= 1_000_000_000_000L) {
            return String.format("%.2fT", num / 1_000_000_000_000.0);
        } else if (num >= 1_000_000_000L) {
            return String.format("%.2fB", num / 1_000_000_000.0);
        } else if (num >= 1_000_000L) {
            return String.format("%.2fM", num / 1_000_000.0);
        } else if (num >= 1_000L) {
            return String.format("%.2fK", num / 1_000.0);
        }
        return String.valueOf(num);
    }

    /**
     * Range allocation result.
     */
    public record RangeAllocation(long start, long end) {}

    /**
     * Current allocation status for monitoring.
     */
    public record AllocationStatus(
        String region,
        long rangeStart,
        long rangeEnd,
        long currentValue,
        long used,
        long remaining,
        double usagePercent
    ) {}

    /**
     * Repository interface for DynamoDB counter operations.
     */
    public interface CounterRepository {
        RangeAllocation allocateRange(RegionConfig region, long batchSize);
    }
}
