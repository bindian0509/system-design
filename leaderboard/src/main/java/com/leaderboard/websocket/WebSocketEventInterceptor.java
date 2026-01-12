package com.leaderboard.websocket;

import java.util.Map;

import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Interceptor for WebSocket handshake.
 * Can be used for authentication, rate limiting, etc.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class WebSocketEventInterceptor implements HandshakeInterceptor {

    @Override
    public boolean beforeHandshake(ServerHttpRequest request, ServerHttpResponse response,
            WebSocketHandler wsHandler, Map<String, Object> attributes) throws Exception {

        // Extract player ID from query params or headers if present
        String query = request.getURI().getQuery();
        if (query != null && query.contains("playerId=")) {
            String playerId = extractParam(query, "playerId");
            if (playerId != null) {
                attributes.put("playerId", playerId);
                log.debug("WebSocket handshake for player: {}", playerId);
            }
        }

        // Could add authentication checks here
        // Could add rate limiting for connections

        return true;
    }

    @Override
    public void afterHandshake(ServerHttpRequest request, ServerHttpResponse response,
            WebSocketHandler wsHandler, Exception exception) {

        if (exception != null) {
            log.error("WebSocket handshake failed", exception);
        }
    }

    private String extractParam(String query, String paramName) {
        String prefix = paramName + "=";
        int start = query.indexOf(prefix);
        if (start == -1) return null;

        start += prefix.length();
        int end = query.indexOf("&", start);

        return end == -1 ? query.substring(start) : query.substring(start, end);
    }
}
