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
 * Fixed Window rate limiting algorithm implementation.
 *
 * <p>This is the simplest rate limiting algorithm. It divides time into
 * fixed windows and counts requests within each window. The counter resets
 * at the start of each new window.
 *
 * <p>Note: This algorithm has an edge case where a user can make 2x the
 * rate limit requests if they time requests around the window boundary.
 * Use SlidingWindowCounter for better accuracy.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class FixedWindow implements RateLimitAlgorithm {

    private final RateLimitRepository repository;

    @Override
    public AlgorithmType getType() {
        return AlgorithmType.FIXED_WINDOW;
    }

    @Override
    public RateLimitResult checkAndIncrement(RateLimitKey key, RateLimitRule rule, int weight) {
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();
        long windowStart = (now / windowSizeSeconds) * windowSizeSeconds;

        long currentCount = repository.getCount(key, rule, windowStart);

        if (currentCount + weight > rule.maxRequests()) {
            log.debug("Rate limit exceeded for key {}: {} + {} > {}",
                key, currentCount, weight, rule.maxRequests());

            Instant resetTime = Instant.ofEpochSecond(windowStart + windowSizeSeconds);
            return RateLimitResult.rejected(
                currentCount,
                rule.maxRequests(),
                resetTime,
                rule.id(),
                rule.name()
            );
        }

        long newCount = repository.increment(key, rule, windowStart, weight);
        Instant resetTime = Instant.ofEpochSecond(windowStart + windowSizeSeconds);

        return RateLimitResult.allowed(newCount, rule.maxRequests(), resetTime);
    }

    @Override
    public RateLimitResult check(RateLimitKey key, RateLimitRule rule) {
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();
        long windowStart = (now / windowSizeSeconds) * windowSizeSeconds;

        long currentCount = repository.getCount(key, rule, windowStart);
        Instant resetTime = Instant.ofEpochSecond(windowStart + windowSizeSeconds);

        if (currentCount >= rule.maxRequests()) {
            return RateLimitResult.rejected(
                currentCount,
                rule.maxRequests(),
                resetTime,
                rule.id(),
                rule.name()
            );
        }

        return RateLimitResult.allowed(currentCount, rule.maxRequests(), resetTime);
    }

    @Override
    public long getCurrentCount(RateLimitKey key, RateLimitRule rule) {
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();
        long windowStart = (now / windowSizeSeconds) * windowSizeSeconds;

        return repository.getCount(key, rule, windowStart);
    }

    @Override
    public void reset(RateLimitKey key, RateLimitRule rule) {
        long now = System.currentTimeMillis() / 1000;
        long windowSizeSeconds = rule.windowSizeSeconds();
        long windowStart = (now / windowSizeSeconds) * windowSizeSeconds;

        repository.reset(key, rule, windowStart);
    }
}
