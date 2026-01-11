package com.urlshortener.security;

import com.urlshortener.domain.UserTier;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * Filter to authenticate requests using API Key or Bearer token
 */
@Slf4j
@Component
public class ApiKeyAuthFilter extends OncePerRequestFilter {

    private static final String AUTH_HEADER = "Authorization";
    private static final String API_KEY_PREFIX = "ApiKey ";
    private static final String BEARER_PREFIX = "Bearer ";

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        String authHeader = request.getHeader(AUTH_HEADER);

        if (authHeader != null) {
            AuthenticatedUser user = null;

            if (authHeader.startsWith(BEARER_PREFIX)) {
                user = validateBearerToken(authHeader.substring(BEARER_PREFIX.length()));
            } else if (authHeader.startsWith(API_KEY_PREFIX)) {
                user = validateApiKey(authHeader.substring(API_KEY_PREFIX.length()));
            }

            if (user != null) {
                UsernamePasswordAuthenticationToken auth =
                    new UsernamePasswordAuthenticationToken(user, null, user.getAuthorities());
                SecurityContextHolder.getContext().setAuthentication(auth);
                log.debug("Authenticated user: {} with tier: {}", user.getUserId(), user.getTier());
            }
        }

        filterChain.doFilter(request, response);
    }

    /**
     * Validate Bearer token (for development: format is "userId:tier")
     * In production, this would verify JWT signature
     */
    private AuthenticatedUser validateBearerToken(String token) {
        try {
            String[] parts = token.split(":");
            if (parts.length >= 2) {
                String userId = parts[0];
                UserTier tier = parseTier(parts[1]);

                return AuthenticatedUser.builder()
                        .userId(userId)
                        .tier(tier)
                        .scopes(List.of("read", "write"))
                        .build();
            }
        } catch (Exception e) {
            log.warn("Invalid bearer token format: {}", e.getMessage());
        }
        return null;
    }

    /**
     * Validate API Key
     * In production, this would look up the key in database and verify hash
     */
    private AuthenticatedUser validateApiKey(String apiKey) {
        if (apiKey.startsWith("urlsh_sk_")) {
            // For development, accept any properly formatted key
            return AuthenticatedUser.builder()
                    .userId("api_user")
                    .tier(UserTier.PREMIUM)
                    .scopes(List.of("read", "write"))
                    .build();
        }
        return null;
    }

    private UserTier parseTier(String tier) {
        return switch (tier.toLowerCase()) {
            case "premium" -> UserTier.PREMIUM;
            case "enterprise" -> UserTier.ENTERPRISE;
            default -> UserTier.FREE;
        };
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        // Don't filter health checks and public redirect endpoints
        return path.equals("/health") ||
               path.equals("/ready") ||
               path.startsWith("/actuator");
    }
}
