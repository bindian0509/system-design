package com.urlshortener.repository;

import com.urlshortener.config.RegionConfig;
import com.urlshortener.service.GlobalIdGenerator.CounterRepository;
import com.urlshortener.service.GlobalIdGenerator.RangeAllocation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * In-memory counter repository for local development and testing.
 *
 * Simulates the DynamoDB counter behavior without actual AWS calls.
 * Each "allocation" returns a new range from the region's capacity.
 */
@Slf4j
@Repository
@Profile("!aws")
public class InMemoryCounterRepository implements CounterRepository {

    private final ConcurrentHashMap<String, AtomicLong> counters = new ConcurrentHashMap<>();

    @Override
    public RangeAllocation allocateRange(RegionConfig region, long batchSize) {
        String key = region.getAwsRegion();

        // Initialize counter at region's start if not exists
        counters.computeIfAbsent(key, k -> new AtomicLong(region.getRangeStart()));

        AtomicLong counter = counters.get(key);

        // Atomically allocate next range
        long rangeStart = counter.getAndAdd(batchSize);
        long rangeEnd = Math.min(rangeStart + batchSize - 1, region.getRangeEnd());

        // Check bounds
        if (rangeStart > region.getRangeEnd()) {
            throw new IllegalStateException(
                String.format("Region %s exhausted! Max: %d, Requested: %d",
                    region.getAwsRegion(), region.getRangeEnd(), rangeStart));
        }

        log.debug("In-memory allocation for {}: [{}, {}]", key, rangeStart, rangeEnd);

        return new RangeAllocation(rangeStart, rangeEnd);
    }

    /**
     * Reset counter for testing purposes.
     */
    public void reset(RegionConfig region) {
        counters.put(region.getAwsRegion(), new AtomicLong(region.getRangeStart()));
    }

    /**
     * Get current counter value for monitoring.
     */
    public long getCurrentValue(RegionConfig region) {
        return counters.getOrDefault(region.getAwsRegion(),
            new AtomicLong(region.getRangeStart())).get();
    }
}
