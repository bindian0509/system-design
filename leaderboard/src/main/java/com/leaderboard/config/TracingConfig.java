package com.leaderboard.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.filter.CommonsRequestLoggingFilter;

import jakarta.servlet.Filter;

/**
 * Configuration for distributed tracing and request logging.
 */
@Configuration
public class TracingConfig {

    /**
     * Request logging filter for debugging and auditing.
     */
    @Bean
    public Filter requestLoggingFilter() {
        CommonsRequestLoggingFilter filter = new CommonsRequestLoggingFilter();
        filter.setIncludeQueryString(true);
        filter.setIncludePayload(true);
        filter.setMaxPayloadLength(1000);
        filter.setIncludeHeaders(false);
        filter.setAfterMessagePrefix("REQUEST: ");
        return filter;
    }
}
