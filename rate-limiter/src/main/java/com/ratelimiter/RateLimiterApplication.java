package com.ratelimiter;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Main application class for the Distributed Rate Limiter.
 *
 * <p>This application provides a high-performance distributed rate limiting
 * solution for API Gateway scenarios, supporting:
 * <ul>
 *   <li>100K-1M requests per second</li>
 *   <li>Composite rate limiting (user + endpoint)</li>
 *   <li>Best-effort consistency with local caching</li>
 *   <li>Configurable failure modes</li>
 * </ul>
 */
@SpringBootApplication
@EnableCaching
@EnableScheduling
@ConfigurationPropertiesScan
public class RateLimiterApplication {

    public static void main(String[] args) {
        SpringApplication.run(RateLimiterApplication.class, args);
    }
}
