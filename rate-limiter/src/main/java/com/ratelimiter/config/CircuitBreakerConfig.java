package com.ratelimiter.config;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.circuitbreaker.event.CircuitBreakerOnStateTransitionEvent;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Configuration;

/**
 * Circuit breaker configuration and event handling.
 *
 * <p>The circuit breaker protects the rate limiter from Redis failures by:
 * <ul>
 *   <li>Opening after configured failure threshold</li>
 *   <li>Allowing fallback behavior based on failure mode</li>
 *   <li>Automatically attempting recovery</li>
 * </ul>
 */
@Slf4j
@Configuration
@RequiredArgsConstructor
public class CircuitBreakerConfig {

    private final CircuitBreakerRegistry circuitBreakerRegistry;
    private final RateLimiterProperties properties;

    @PostConstruct
    public void init() {
        // Register event consumer for Redis circuit breaker
        CircuitBreaker circuitBreaker = circuitBreakerRegistry.circuitBreaker("redis");

        circuitBreaker.getEventPublisher()
            .onStateTransition(this::onStateTransition);

        log.info("Configured circuit breaker 'redis' with failure mode: {}",
            properties.getFailureMode());
    }

    /**
     * Handles circuit breaker state transitions.
     */
    private void onStateTransition(CircuitBreakerOnStateTransitionEvent event) {
        log.warn("Circuit breaker '{}' transitioned from {} to {}",
            event.getCircuitBreakerName(),
            event.getStateTransition().getFromState(),
            event.getStateTransition().getToState());

        if (event.getStateTransition().getToState() == CircuitBreaker.State.OPEN) {
            log.error("Redis circuit breaker OPEN - rate limiter operating in {} mode",
                properties.getFailureMode());
        } else if (event.getStateTransition().getToState() == CircuitBreaker.State.CLOSED) {
            log.info("Redis circuit breaker CLOSED - normal operation resumed");
        }
    }
}
