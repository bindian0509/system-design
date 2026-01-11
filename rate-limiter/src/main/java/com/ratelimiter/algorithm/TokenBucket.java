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
 * Token Bucket rate limiting algorithm implementation.
 *
 * <p>Tokens are added to a bucket at a fixed rate. Each request consumes one token.
 * Requests are rejected when the bucket is empty. The bucket has a maximum capacity
 * which allows for controlled bursting.
 *
 * <p>Configuration:
 * <ul>
 *   <li>maxRequests: Maximum bucket capacity (burst size)</li>
 *   <li>windowSize: Time to fully refill the bucket</li>
 *   <li>Refill rate: maxRequests / windowSize tokens per second</li>
 * </ul>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class TokenBucket implements RateLimitAlgorithm {

    private final RateLimitRepository repository;

    @Override
    public AlgorithmType getType() {
        return AlgorithmType.TOKEN_BUCKET;
    }

    @Override
    public RateLimitResult checkAndIncrement(RateLimitKey key, RateLimitRule rule, int weight) {
        long now = System.currentTimeMillis();

        // Get current bucket state
        TokenBucketState state = repository.getTokenBucketState(key, rule);

        // Calculate tokens to add based on elapsed time
        long elapsedMs = now - state.lastRefillTime();
        double refillRate = (double) rule.maxRequests() / (rule.windowSizeSeconds() * 1000);
        long tokensToAdd = (long) (elapsedMs * refillRate);

        // Refill bucket (capped at max capacity)
        long availableTokens = Math.min(rule.maxRequests(), state.tokens() + tokensToAdd);

        // Check if enough tokens available
        if (availableTokens < weight) {
            log.debug("Rate limit exceeded for key {}: {} tokens available, {} required",
                key, availableTokens, weight);

            // Calculate when enough tokens will be available
            long tokensNeeded = weight - availableTokens;
            long msUntilAvailable = (long) (tokensNeeded / refillRate);
            Instant resetTime = Instant.ofEpochMilli(now + msUntilAvailable);

            return RateLimitResult.rejected(
                rule.maxRequests() - availableTokens, // Current usage
                rule.maxRequests(),
                resetTime,
                rule.id(),
                rule.name()
            );
        }

        // Consume tokens
        long newTokens = availableTokens - weight;
        repository.setTokenBucketState(key, rule, new TokenBucketState(newTokens, now));

        // Reset time is when bucket would be full again
        long msUntilFull = (long) ((rule.maxRequests() - newTokens) / refillRate);
        Instant resetTime = Instant.ofEpochMilli(now + msUntilFull);

        return RateLimitResult.allowed(
            rule.maxRequests() - newTokens, // Current usage
            rule.maxRequests(),
            resetTime
        );
    }

    @Override
    public RateLimitResult check(RateLimitKey key, RateLimitRule rule) {
        long now = System.currentTimeMillis();

        TokenBucketState state = repository.getTokenBucketState(key, rule);

        long elapsedMs = now - state.lastRefillTime();
        double refillRate = (double) rule.maxRequests() / (rule.windowSizeSeconds() * 1000);
        long tokensToAdd = (long) (elapsedMs * refillRate);
        long availableTokens = Math.min(rule.maxRequests(), state.tokens() + tokensToAdd);

        long msUntilFull = (long) ((rule.maxRequests() - availableTokens) / refillRate);
        Instant resetTime = Instant.ofEpochMilli(now + msUntilFull);

        if (availableTokens < 1) {
            return RateLimitResult.rejected(
                rule.maxRequests() - availableTokens,
                rule.maxRequests(),
                resetTime,
                rule.id(),
                rule.name()
            );
        }

        return RateLimitResult.allowed(
            rule.maxRequests() - availableTokens,
            rule.maxRequests(),
            resetTime
        );
    }

    @Override
    public long getCurrentCount(RateLimitKey key, RateLimitRule rule) {
        long now = System.currentTimeMillis();
        TokenBucketState state = repository.getTokenBucketState(key, rule);

        long elapsedMs = now - state.lastRefillTime();
        double refillRate = (double) rule.maxRequests() / (rule.windowSizeSeconds() * 1000);
        long tokensToAdd = (long) (elapsedMs * refillRate);
        long availableTokens = Math.min(rule.maxRequests(), state.tokens() + tokensToAdd);

        return rule.maxRequests() - availableTokens;
    }

    @Override
    public void reset(RateLimitKey key, RateLimitRule rule) {
        repository.setTokenBucketState(key, rule, new TokenBucketState(rule.maxRequests(), System.currentTimeMillis()));
    }

    /**
     * Represents the state of a token bucket.
     */
    public record TokenBucketState(long tokens, long lastRefillTime) {
        public static TokenBucketState initial(int maxTokens) {
            return new TokenBucketState(maxTokens, System.currentTimeMillis());
        }
    }
}
