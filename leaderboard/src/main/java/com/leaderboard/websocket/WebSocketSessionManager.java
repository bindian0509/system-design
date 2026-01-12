package com.leaderboard.websocket;

import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.event.EventListener;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.messaging.SessionConnectedEvent;
import org.springframework.web.socket.messaging.SessionDisconnectEvent;
import org.springframework.web.socket.messaging.SessionSubscribeEvent;
import org.springframework.web.socket.messaging.SessionUnsubscribeEvent;

import com.leaderboard.metrics.LeaderboardMetrics;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Manages WebSocket sessions and subscriptions.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class WebSocketSessionManager {

    private final LeaderboardMetrics metrics;

    // Map of session ID to player ID
    private final Map<String, String> sessionToPlayer = new ConcurrentHashMap<>();

    // Map of player ID to session IDs (one player may have multiple sessions)
    private final Map<String, Set<String>> playerToSessions = new ConcurrentHashMap<>();

    // Map of destination to session IDs (for targeted broadcasts)
    private final Map<String, Set<String>> destinationToSessions = new ConcurrentHashMap<>();

    /**
     * Handle new WebSocket connection.
     */
    @EventListener
    public void handleSessionConnected(SessionConnectedEvent event) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(event.getMessage());
        String sessionId = accessor.getSessionId();

        log.info("WebSocket session connected: {}", sessionId);
        metrics.incrementWebsocketConnections();
    }

    /**
     * Handle WebSocket disconnection.
     */
    @EventListener
    public void handleSessionDisconnect(SessionDisconnectEvent event) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(event.getMessage());
        String sessionId = accessor.getSessionId();

        // Clean up session mappings
        String playerId = sessionToPlayer.remove(sessionId);
        if (playerId != null) {
            Set<String> sessions = playerToSessions.get(playerId);
            if (sessions != null) {
                sessions.remove(sessionId);
                if (sessions.isEmpty()) {
                    playerToSessions.remove(playerId);
                }
            }
        }

        // Clean up destination subscriptions
        destinationToSessions.forEach((dest, sessions) -> sessions.remove(sessionId));

        log.info("WebSocket session disconnected: {}", sessionId);
        metrics.incrementWebsocketDisconnections();
    }

    /**
     * Handle new subscription.
     */
    @EventListener
    public void handleSessionSubscribe(SessionSubscribeEvent event) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(event.getMessage());
        String sessionId = accessor.getSessionId();
        String destination = accessor.getDestination();

        if (destination != null) {
            destinationToSessions.computeIfAbsent(destination, k -> ConcurrentHashMap.newKeySet())
                .add(sessionId);

            log.debug("Session {} subscribed to {}", sessionId, destination);
        }
    }

    /**
     * Handle unsubscription.
     */
    @EventListener
    public void handleSessionUnsubscribe(SessionUnsubscribeEvent event) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(event.getMessage());
        String sessionId = accessor.getSessionId();
        String subscriptionId = accessor.getSubscriptionId();

        log.debug("Session {} unsubscribed from subscription {}", sessionId, subscriptionId);
    }

    /**
     * Register a player ID for a session.
     */
    public void registerPlayer(String sessionId, String playerId) {
        sessionToPlayer.put(sessionId, playerId);
        playerToSessions.computeIfAbsent(playerId, k -> ConcurrentHashMap.newKeySet())
            .add(sessionId);

        log.debug("Registered player {} for session {}", playerId, sessionId);
    }

    /**
     * Get all sessions for a player.
     */
    public Set<String> getSessionsForPlayer(String playerId) {
        return playerToSessions.getOrDefault(playerId, Set.of());
    }

    /**
     * Get all sessions subscribed to a destination.
     */
    public Set<String> getSessionsForDestination(String destination) {
        return destinationToSessions.getOrDefault(destination, Set.of());
    }

    /**
     * Get the player ID for a session.
     */
    public String getPlayerForSession(String sessionId) {
        return sessionToPlayer.get(sessionId);
    }

    /**
     * Get total active sessions.
     */
    public int getActiveSessions() {
        return sessionToPlayer.size();
    }

    /**
     * Get total unique connected players.
     */
    public int getConnectedPlayers() {
        return playerToSessions.size();
    }
}
