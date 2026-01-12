package com.leaderboard.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryRegistry;
import lombok.extern.slf4j.Slf4j;

/**
 * Configuration for circuit breakers and retry policies.
 */
@Slf4j
@Configuration
public class CircuitBreakerConfig {

    /**
     * Get the Redis circuit breaker.
     */
    @Bean
    public CircuitBreaker redisCircuitBreaker(CircuitBreakerRegistry circuitBreakerRegistry) {
        CircuitBreaker circuitBreaker = circuitBreakerRegistry.circuitBreaker("redis");

        circuitBreaker.getEventPublisher()
            .onStateTransition(event ->
                log.warn("Redis circuit breaker state transition: {} -> {}",
                    event.getStateTransition().getFromState(),
                    event.getStateTransition().getToState()))
            .onError(event ->
                log.error("Redis circuit breaker error: {}",
                    event.getThrowable().getMessage()))
            .onSuccess(event ->
                log.trace("Redis circuit breaker success: {}ms",
                    event.getElapsedDuration().toMillis()));

        return circuitBreaker;
    }

    /**
     * Get the Kafka circuit breaker.
     */
    @Bean
    public CircuitBreaker kafkaCircuitBreaker(CircuitBreakerRegistry circuitBreakerRegistry) {
        CircuitBreaker circuitBreaker = circuitBreakerRegistry.circuitBreaker("kafka");

        circuitBreaker.getEventPublisher()
            .onStateTransition(event ->
                log.warn("Kafka circuit breaker state transition: {} -> {}",
                    event.getStateTransition().getFromState(),
                    event.getStateTransition().getToState()));

        return circuitBreaker;
    }

    /**
     * Get the Redis retry policy.
     */
    @Bean
    public Retry redisRetry(RetryRegistry retryRegistry) {
        Retry retry = retryRegistry.retry("redis");

        retry.getEventPublisher()
            .onRetry(event ->
                log.warn("Redis retry attempt {} due to: {}",
                    event.getNumberOfRetryAttempts(),
                    event.getLastThrowable().getMessage()));

        return retry;
    }

    /**
     * Get the Kafka retry policy.
     */
    @Bean
    public Retry kafkaRetry(RetryRegistry retryRegistry) {
        Retry retry = retryRegistry.retry("kafka");

        retry.getEventPublisher()
            .onRetry(event ->
                log.warn("Kafka retry attempt {} due to: {}",
                    event.getNumberOfRetryAttempts(),
                    event.getLastThrowable().getMessage()));

        return retry;
    }
}
