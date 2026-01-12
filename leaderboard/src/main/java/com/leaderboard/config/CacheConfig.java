package com.leaderboard.config;

import java.util.concurrent.TimeUnit;

import org.springframework.cache.CacheManager;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import com.github.benmanes.caffeine.cache.Caffeine;

@Configuration
public class CacheConfig {

    public static final String LEADERBOARD_TOP_CACHE = "leaderboard-top";
    public static final String PLAYER_RANK_CACHE = "player-rank";
    public static final String PLAYER_PROFILE_CACHE = "player-profile";

    @Bean
    @Primary
    public CacheManager cacheManager() {
        CaffeineCacheManager cacheManager = new CaffeineCacheManager();
        cacheManager.setCaffeine(Caffeine.newBuilder()
            .maximumSize(10000)
            .expireAfterWrite(1, TimeUnit.SECONDS)
            .recordStats());
        return cacheManager;
    }

    @Bean
    public CacheManager longLivedCacheManager() {
        CaffeineCacheManager cacheManager = new CaffeineCacheManager(PLAYER_PROFILE_CACHE);
        cacheManager.setCaffeine(Caffeine.newBuilder()
            .maximumSize(50000)
            .expireAfterWrite(5, TimeUnit.MINUTES)
            .recordStats());
        return cacheManager;
    }
}
