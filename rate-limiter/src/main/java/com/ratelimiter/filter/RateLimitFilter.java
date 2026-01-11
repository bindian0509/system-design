package com.ratelimiter.filter;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ratelimiter.config.RateLimiterProperties;
import com.ratelimiter.domain.RateLimitResult;
import com.ratelimiter.service.RateLimiterService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * HTTP filter that applies rate limiting to incoming requests.
 *
 * <p>This filter intercepts all requests and:
 * <ul>
 *   <li>Extracts user ID from headers/authentication</li>
 *   <li>Checks rate limits against configured rules</li>
 *   <li>Adds rate limit headers to responses</li>
 *   <li>Returns 429 for rejected requests</li>
 * </ul>
 */
@Slf4j
@Component
@Order(1)
@RequiredArgsConstructor
public class RateLimitFilter extends OncePerRequestFilter {

    private final RateLimiterService rateLimiterService;
    private final RateLimiterProperties properties;
    private final ObjectMapper objectMapper;

    // Paths to exclude from rate limiting
    private static final Set<String> EXCLUDED_PATHS = Set.of(
        "/health",
        "/ready",
        "/actuator/health",
        "/actuator/prometheus",
        "/actuator/info"
    );

    // Header names for user identification
    private static final String HEADER_USER_ID = "X-User-ID";
    private static final String HEADER_API_KEY = "X-API-Key";
    private static final String HEADER_TENANT_ID = "X-Tenant-ID";
    private static final String HEADER_FORWARDED_FOR = "X-Forwarded-For";

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        if (!properties.isEnabled()) {
            filterChain.doFilter(request, response);
            return;
        }

        // Extract identifiers from request
        String userId = extractUserId(request);
        String endpoint = request.getRequestURI();
        String ipAddress = extractIpAddress(request);
        String tenantId = request.getHeader(HEADER_TENANT_ID);

        // Check rate limit
        RateLimitResult result = rateLimiterService.checkRateLimit(
            userId, endpoint, ipAddress, tenantId, 1);

        // Add rate limit headers
        addRateLimitHeaders(response, result);

        if (!result.allowed()) {
            log.warn("Rate limit exceeded for user={}, ip={}, endpoint={}, rule={}",
                userId, ipAddress, endpoint, result.violatedRuleId());

            response.setStatus(HttpServletResponse.SC_TOO_MANY_REQUESTS);
            response.setContentType("application/json");
            response.setHeader("Retry-After", String.valueOf(result.retryAfterSeconds()));

            Map<String, Object> errorBody = new HashMap<>();
            errorBody.put("error", "Rate Limit Exceeded");
            errorBody.put("code", "RATE_LIMITED");
            errorBody.put("retryAfter", result.retryAfterSeconds());
            errorBody.put("limit", result.limit());
            errorBody.put("remaining", result.remainingRequests());

            if (result.violatedRuleId() != null) {
                errorBody.put("violatedRule", result.violatedRuleId());
            }

            objectMapper.writeValue(response.getWriter(), errorBody);
            return;
        }

        filterChain.doFilter(request, response);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return EXCLUDED_PATHS.stream().anyMatch(path::startsWith);
    }

    /**
     * Extracts user ID from request headers.
     * Priority: X-User-ID > X-API-Key > null
     */
    private String extractUserId(HttpServletRequest request) {
        String userId = request.getHeader(HEADER_USER_ID);
        if (userId != null && !userId.isBlank()) {
            return userId;
        }

        String apiKey = request.getHeader(HEADER_API_KEY);
        if (apiKey != null && !apiKey.isBlank()) {
            return "apikey:" + apiKey;
        }

        return null;
    }

    /**
     * Extracts client IP address from request.
     * Handles X-Forwarded-For header for proxied requests.
     */
    private String extractIpAddress(HttpServletRequest request) {
        String xForwardedFor = request.getHeader(HEADER_FORWARDED_FOR);
        if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
            // Take the first IP in the chain (original client)
            return xForwardedFor.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    /**
     * Adds rate limit headers to the response.
     */
    private void addRateLimitHeaders(HttpServletResponse response, RateLimitResult result) {
        response.setHeader("X-RateLimit-Limit", String.valueOf(result.limit()));
        response.setHeader("X-RateLimit-Remaining", String.valueOf(result.remainingRequests()));
        response.setHeader("X-RateLimit-Reset", String.valueOf(result.resetTimeEpochSeconds()));
    }
}
