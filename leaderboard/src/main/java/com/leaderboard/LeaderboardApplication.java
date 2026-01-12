package com.leaderboard;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.scheduling.annotation.EnableScheduling;

import com.leaderboard.config.LeaderboardProperties;

@SpringBootApplication
@EnableCaching
@EnableKafka
@EnableScheduling
@EnableConfigurationProperties(LeaderboardProperties.class)
public class LeaderboardApplication {

    public static void main(String[] args) {
        SpringApplication.run(LeaderboardApplication.class, args);
    }
}
