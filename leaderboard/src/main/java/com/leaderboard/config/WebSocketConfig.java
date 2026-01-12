package com.leaderboard.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

import lombok.RequiredArgsConstructor;

@Configuration
@EnableWebSocketMessageBroker
@RequiredArgsConstructor
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    private final LeaderboardProperties properties;

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // Enable simple broker for topics
        registry.enableSimpleBroker("/topic");
        // Prefix for messages bound to @MessageMapping methods
        registry.setApplicationDestinationPrefixes("/app");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        // Register STOMP endpoint with SockJS fallback
        registry.addEndpoint(properties.getWebsocket().getEndpoint())
            .setAllowedOriginPatterns("*")
            .withSockJS();

        // Also register without SockJS for native WebSocket clients
        registry.addEndpoint(properties.getWebsocket().getEndpoint())
            .setAllowedOriginPatterns("*");
    }
}
