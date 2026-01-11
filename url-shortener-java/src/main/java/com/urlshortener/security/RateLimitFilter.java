package com.urlshortener.security;

import com.urlshortener.exception.RateLimitExceededException;
import com.urlshortener.service.CacheService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Rate limiting filter using token bucket algorithm
 */
@Slf4j
@Component
@Order(1)
@RequiredArgsConstructor
public class RateLimitFilter extends OncePerRequestFilter {

    private final CacheService cacheService;

    @Value("${url-shortener.rate-limit.enabled:true}")
    private boolean enabled;

    @Value("${url-shortener.rate-limit.requests-per-minute:60}")
    private int defaultRequestsPerMinute;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        if (!enabled) {
            filterChain.doFilter(request, response);
            return;
        }

        String identifier = getIdentifier(request);
        int limit = getLimit();

        long count = cacheService.incrementRateLimit(identifier, 60);

        // Add rate limit headers
        response.setHeader("X-RateLimit-Limit", String.valueOf(limit));
        response.setHeader("X-RateLimit-Remaining", String.valueOf(Math.max(0, limit - count)));
        response.setHeader("X-RateLimit-Reset", String.valueOf(System.currentTimeMillis() / 1000 + 60));

        if (count > limit) {
            log.warn("Rate limit exceeded for: {}", identifier);
            response.setStatus(429);
            response.setContentType("application/json");
            response.getWriter().write("{\"error\":\"Rate limit exceeded\",\"code\":\"RATE_LIMITED\"}");
            return;
        }

        filterChain.doFilter(request, response);
    }

    private String getIdentifier(HttpServletRequest request) {
        // Use authenticated user ID if available
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof AuthenticatedUser user) {
            return "user:" + user.getUserId();
        }

        // Fallback to IP address
        String ip = getClientIp(request);
        return "ip:" + ip;
    }

    private int getLimit() {
        // Use tier-specific limit if authenticated
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof AuthenticatedUser user) {
            return user.getTier().getRequestsPerMinute();
        }
        return defaultRequestsPerMinute;
    }

    private String getClientIp(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
            return xForwardedFor.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        // Don't rate limit health checks
        return path.equals("/health") ||
               path.equals("/ready") ||
               path.startsWith("/actuator");
    }
}
