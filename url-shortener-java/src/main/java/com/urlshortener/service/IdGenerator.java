package com.urlshortener.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import java.security.SecureRandom;
import java.util.concurrent.atomic.AtomicLong;

/**
 * ID Generator using Base62 encoding with distributed range allocation.
 *
 * This implements the same algorithm as the Rust version:
 * - Each instance gets a range of IDs (default 1M)
 * - Local atomic counter for zero-coordination writes
 * - Range refresh from DynamoDB when threshold reached
 * - Base62 encoding: 0-9, a-z, A-Z (62 chars)
 *
 * Capacity: 62^7 = 3,521,614,606,208 unique codes
 * At 500M/month = 7,000+ years of capacity
 */
@Slf4j
@Component
public class IdGenerator {

    private static final String CHARSET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
    private static final int BASE = 62;

    @Value("${url-shortener.code-length:7}")
    private int codeLength;

    @Value("${url-shortener.id-generator.range-size:1000000}")
    private long rangeSize;

    @Value("${url-shortener.id-generator.prefetch-threshold:0.9}")
    private double prefetchThreshold;

    private final AtomicLong counter = new AtomicLong(0);
    private volatile long rangeStart = 0;
    private volatile long rangeEnd = Long.MAX_VALUE;
    private final SecureRandom random = new SecureRandom();

    // For distributed mode - would be injected
    private CounterService counterService;

    @PostConstruct
    public void init() {
        log.info("IdGenerator initialized with code length: {}, range size: {}",
                 codeLength, rangeSize);
    }

    /**
     * Set counter service for distributed range allocation
     */
    public void setCounterService(CounterService counterService) {
        this.counterService = counterService;
    }

    /**
     * Initialize with a specific range (for distributed deployment)
     */
    public void initializeRange(long start, long end) {
        this.rangeStart = start;
        this.rangeEnd = end;
        this.counter.set(start);
        log.info("Range initialized: {} to {}", start, end);
    }

    /**
     * Generate a new unique short code
     */
    public String generate() {
        long value = counter.getAndIncrement();

        // Check if we need to refresh the range
        if (value >= rangeEnd) {
            synchronized (this) {
                // Double-check after acquiring lock
                if (counter.get() >= rangeEnd) {
                    refreshRange();
                    value = counter.getAndIncrement();
                }
            }
        }

        // Check if approaching threshold (async prefetch)
        if (shouldPrefetch(value)) {
            asyncPrefetchRange();
        }

        return encode(value);
    }

    /**
     * Generate a random short code (fallback for collisions)
     */
    public String generateRandom() {
        StringBuilder sb = new StringBuilder(codeLength);
        for (int i = 0; i < codeLength; i++) {
            sb.append(CHARSET.charAt(random.nextInt(BASE)));
        }
        return sb.toString();
    }

    /**
     * Encode a number to Base62 string
     */
    public String encode(long num) {
        if (num == 0) {
            return pad("0");
        }

        StringBuilder sb = new StringBuilder();
        while (num > 0) {
            int remainder = (int) (num % BASE);
            sb.insert(0, CHARSET.charAt(remainder));
            num /= BASE;
        }

        return pad(sb.toString());
    }

    /**
     * Decode a Base62 string to number
     */
    public Long decode(String code) {
        if (code == null || code.isEmpty()) {
            return null;
        }

        long result = 0;
        for (char c : code.toCharArray()) {
            int value = charToValue(c);
            if (value < 0) {
                return null;
            }
            result = result * BASE + value;
        }
        return result;
    }

    /**
     * Validate a short code format
     */
    public boolean isValidCode(String code) {
        if (code == null || code.length() != codeLength) {
            return false;
        }
        return code.chars().allMatch(c ->
            (c >= '0' && c <= '9') ||
            (c >= 'a' && c <= 'z') ||
            (c >= 'A' && c <= 'Z')
        );
    }

    /**
     * Validate a custom alias
     */
    public boolean isValidCustomAlias(String alias, int maxLength) {
        if (alias == null || alias.length() < 4 || alias.length() > maxLength) {
            return false;
        }
        // Must be alphanumeric or hyphens
        if (!alias.matches("^[a-zA-Z0-9-]+$")) {
            return false;
        }
        // Cannot start or end with hyphen
        if (alias.startsWith("-") || alias.endsWith("-")) {
            return false;
        }
        // Cannot have consecutive hyphens
        if (alias.contains("--")) {
            return false;
        }
        return true;
    }

    /**
     * Get current counter value (for monitoring)
     */
    public long getCurrentCounter() {
        return counter.get();
    }

    /**
     * Get remaining IDs in current range
     */
    public long getRemainingInRange() {
        return Math.max(0, rangeEnd - counter.get());
    }

    // Private helper methods

    private String pad(String code) {
        if (code.length() >= codeLength) {
            return code;
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < codeLength - code.length(); i++) {
            sb.append('0');
        }
        sb.append(code);
        return sb.toString();
    }

    private int charToValue(char c) {
        if (c >= '0' && c <= '9') {
            return c - '0';
        } else if (c >= 'a' && c <= 'z') {
            return c - 'a' + 10;
        } else if (c >= 'A' && c <= 'Z') {
            return c - 'A' + 36;
        }
        return -1;
    }

    private boolean shouldPrefetch(long value) {
        long threshold = rangeStart + (long) ((rangeEnd - rangeStart) * prefetchThreshold);
        return value >= threshold && counterService != null;
    }

    private void asyncPrefetchRange() {
        // In production, this would be async
        log.debug("Would prefetch next range asynchronously");
    }

    private void refreshRange() {
        if (counterService != null) {
            // Production: Get new range from DynamoDB
            try {
                long[] newRange = counterService.allocateRange(rangeSize);
                this.rangeStart = newRange[0];
                this.rangeEnd = newRange[1];
                this.counter.set(rangeStart);
                log.info("Range refreshed from counter service: {} to {}", rangeStart, rangeEnd);
            } catch (Exception e) {
                log.error("Failed to refresh range, using random fallback", e);
                // Fallback: use random offset
                fallbackRangeRefresh();
            }
        } else {
            // Local mode: just wrap around with random offset
            fallbackRangeRefresh();
        }
    }

    private void fallbackRangeRefresh() {
        long randomOffset = Math.abs(random.nextLong()) % rangeSize;
        this.rangeStart = randomOffset;
        this.rangeEnd = rangeStart + rangeSize;
        this.counter.set(rangeStart);
        log.warn("Using fallback range: {} to {}", rangeStart, rangeEnd);
    }

    /**
     * Interface for distributed counter service
     */
    public interface CounterService {
        /**
         * Atomically allocate a range of IDs
         * @param size Number of IDs to allocate
         * @return Array of [start, end) for the allocated range
         */
        long[] allocateRange(long size);
    }
}
