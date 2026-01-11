package com.ratelimiter.algorithm;

import com.ratelimiter.domain.RateLimitKey;
import com.ratelimiter.domain.RateLimitResult;
import com.ratelimiter.domain.RateLimitRule;
import com.ratelimiter.repository.RateLimitRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.Instant;

/**
 * Sliding Window Counter rate limiting algorithm implementation.
 *
 * <p>This algorithm provides high accuracy (~99.7%) with O(1) memory and time complexity
 * by using weighted counts from the current and previous time windows.
 *
 * <p>Formula: weightedCount = previousCount * weight + currentCount
 * where weight = (windowSize - elapsedTimeInCurrentWindow) / windowSize
 *
 * <p>Example:
 * <ul>
 *   <li>Window size: 60 seconds</li>
 *   <li>Current time: 45 seconds into current window (75% through)</li>
 *   <li>Previous window count: 80</li>
 *   <li>Current window count: 30</li>
 *   <li>Weight for previous: 1 - 0.75 = 0.25</li>
 *   <li>Weighted count: 80 * 0.25 + 30 = 50</li>
 * </ul>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class SlidingWindowCounter implements RateLimitAlgorithm {

    private final RateLimitRepository repository;

    @Override
    public AlgorithmType getType() {
        return AlgorithmType.SLIDING_WINDOW_COUNTER;
    }

    @Override
    public RateLimitResult checkAndIncrement(RateLimitKey key, RateLimitRule rule, int weight) {
        long now = System.currentTimeMillis() / 1000; // Current time in seconds
        long windowSizeSeconds = rule.windowSizeSeconds();

        // Calculate window boundaries
        long currentWindowStart = (now / windowSizeSeconds) * windowSizeSeconds;
        long previousWindowStart = currentWindowStart - windowSizeSeconds;

        // Get counts from repository
        long currentCount = repository.getCount(key, rule, currentWindowStart);
        long previousCount = repository.getCount(key, rule, previousWindowStart);

        // Calculate weighted count
        double elapsedRatio = (double)(now - currentWindowStart) / windowSizeSeconds;
        double previousWeight = 1.0 - elapsedRatio;
        long weightedCount = (long)(previousCount * previousWeight) + currentCount;

        // Check if limit would be exceeded
        if (weightedCount + weight > rule.maxRequests()) {
            log.debug("Rate limit exceeded for key {}: {} + {} > {}",
                key, weightedCount, weight, rule.maxRequests());

            Instant resetTime = Instant.ofEpochSecond(currentWindowStart + windowSizeSeconds);
            return RateLimitResult.rejected(
                weightedCount,
                rule.maxRequests(),
                resetTime,
                rule.id(),
                rule.name()
            );
        }

        // Increment counter
        long newCount = repository.increment(key, rule, currentWindowStart, weight);
        long newWeightedCount = (long)(previousCount * previousWeight) + newCount;

        Instant resetTime = Instant.ofEpochSecond(currentWindowStart + windowSizeSeconds);
        return RateLimitResult.allowed(newWeightedCount, rule.maxRequests(), resetTime);
    }

    @Override
    public RateLimitResult check(RateLimitKey key, RateLimitRule rule) {
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();

        long currentWindowStart = (now / windowSizeSeconds) * windowSizeSeconds;
        long previousWindowStart = currentWindowStart - windowSizeSeconds;

        long currentCount = repository.getCount(key, rule, currentWindowStart);
        long previousCount = repository.getCount(key, rule, previousWindowStart);

        double elapsedRatio = (double)(now - currentWindowStart) / windowSizeSeconds;
        double previousWeight = 1.0 - elapsedRatio;
        long weightedCount = (long)(previousCount * previousWeight) + currentCount;

        Instant resetTime = Instant.ofEpochSecond(currentWindowStart + windowSizeSeconds);

        if (weightedCount >= rule.maxRequests()) {
            return RateLimitResult.rejected(
                weightedCount,
                rule.maxRequests(),
                resetTime,
                rule.id(),
                rule.name()
            );
        }

        return RateLimitResult.allowed(weightedCount, rule.maxRequests(), resetTime);
    }

    @Override
    public long getCurrentCount(RateLimitKey key, RateLimitRule rule) {
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();

        long currentWindowStart = (now / windowSizeSeconds) * windowSizeSeconds;
        long previousWindowStart = currentWindowStart - windowSizeSeconds;

        long currentCount = repository.getCount(key, rule, currentWindowStart);
        long previousCount = repository.getCount(key, rule, previousWindowStart);

        double elapsedRatio = (double)(now - currentWindowStart) / windowSizeSeconds;
        double previousWeight = 1.0 - elapsedRatio;

        return (long)(previousCount * previousWeight) + currentCount;
    }

    @Override
    public void reset(RateLimitKey key, RateLimitRule rule) {
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();

        long currentWindowStart = (now / windowSizeSeconds) * windowSizeSeconds;
        long previousWindowStart = currentWindowStart - windowSizeSeconds;

        repository.reset(key, rule, currentWindowStart);
        repository.reset(key, rule, previousWindowStart);
    }
}
