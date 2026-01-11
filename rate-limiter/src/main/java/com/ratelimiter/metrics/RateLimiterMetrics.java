package com.ratelimiter.metrics;

import com.ratelimiter.cache.LocalCacheService;
import io.micrometer.core.instrument.*;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Metrics collection for the rate limiter.
 *
 * <p>Exposes the following metrics via Micrometer:
 * <ul>
 *   <li>ratelimit_requests_total - Total requests processed</li>
 *   <li>ratelimit_requests_allowed - Requests allowed through</li>
 *   <li>ratelimit_requests_rejected - Requests rejected (429)</li>
 *   <li>ratelimit_check_latency_seconds - Rate limit check duration</li>
 *   <li>ratelimit_cache_hits_total - Local cache hits</li>
 *   <li>ratelimit_cache_misses_total - Local cache misses</li>
 *   <li>ratelimit_redis_errors_total - Redis operation failures</li>
 * </ul>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class RateLimiterMetrics {

    private final MeterRegistry meterRegistry;
    private final LocalCacheService localCacheService;

    private Counter totalRequests;
    private Counter allowedRequests;
    private Counter rejectedRequests;
    private Counter redisErrors;
    private Timer checkLatency;

    private final AtomicLong cacheHitRate = new AtomicLong(0);

    @PostConstruct
    public void init() {
        // Request counters
        totalRequests = Counter.builder("ratelimit.requests.total")
            .description("Total rate limit checks performed")
            .register(meterRegistry);

        allowedRequests = Counter.builder("ratelimit.requests.allowed")
            .description("Requests allowed through rate limiter")
            .register(meterRegistry);

        rejectedRequests = Counter.builder("ratelimit.requests.rejected")
            .description("Requests rejected by rate limiter")
            .register(meterRegistry);

        redisErrors = Counter.builder("ratelimit.redis.errors.total")
            .description("Redis operation failures")
            .register(meterRegistry);

        // Latency histogram
        checkLatency = Timer.builder("ratelimit.check.latency")
            .description("Rate limit check latency")
            .publishPercentiles(0.5, 0.9, 0.95, 0.99)
            .register(meterRegistry);

        // Cache gauges
        Gauge.builder("ratelimit.cache.hit_rate", cacheHitRate, AtomicLong::doubleValue)
            .description("Local cache hit rate percentage")
            .register(meterRegistry);

        Gauge.builder("ratelimit.cache.size", localCacheService,
                svc -> svc.getStats().estimatedSize())
            .description("Local cache current size")
            .register(meterRegistry);

        Gauge.builder("ratelimit.cache.pending_syncs", localCacheService,
                svc -> svc.getStats().pendingSyncCount())
            .description("Pending syncs to Redis")
            .register(meterRegistry);

        log.info("Initialized rate limiter metrics");
    }

    /**
     * Records an allowed request.
     */
    public void recordAllowed(String ruleId) {
        totalRequests.increment();
        allowedRequests.increment();

        Counter.builder("ratelimit.requests.allowed.by_rule")
            .tag("rule", ruleId != null ? ruleId : "none")
            .register(meterRegistry)
            .increment();

        updateCacheMetrics();
    }

    /**
     * Records a rejected request.
     */
    public void recordRejected(String ruleId) {
        totalRequests.increment();
        rejectedRequests.increment();

        Counter.builder("ratelimit.requests.rejected.by_rule")
            .tag("rule", ruleId != null ? ruleId : "unknown")
            .register(meterRegistry)
            .increment();

        updateCacheMetrics();
    }

    /**
     * Records the latency of a rate limit check.
     */
    public void recordLatency(long nanos) {
        checkLatency.record(nanos, TimeUnit.NANOSECONDS);
    }

    /**
     * Records a Redis error.
     */
    public void recordError() {
        redisErrors.increment();
    }

    /**
     * Records cache statistics.
     */
    private void updateCacheMetrics() {
        var stats = localCacheService.getStats();
        cacheHitRate.set((long) (stats.hitRate() * 100));
    }

    /**
     * Gets summary statistics.
     */
    public MetricsSummary getSummary() {
        var cacheStats = localCacheService.getStats();

        return new MetricsSummary(
            (long) totalRequests.count(),
            (long) allowedRequests.count(),
            (long) rejectedRequests.count(),
            (long) redisErrors.count(),
            checkLatency.mean(TimeUnit.MILLISECONDS),
            checkLatency.percentile(0.99, TimeUnit.MILLISECONDS),
            cacheStats.hitRate(),
            cacheStats.estimatedSize()
        );
    }

    /**
     * Metrics summary record.
     */
    public record MetricsSummary(
        long totalRequests,
        long allowedRequests,
        long rejectedRequests,
        long redisErrors,
        double avgLatencyMs,
        double p99LatencyMs,
        double cacheHitRate,
        long cacheSize
    ) {}
}
