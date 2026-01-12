package com.leaderboard.controller;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.leaderboard.domain.dto.ScoreSubmission;
import com.leaderboard.domain.dto.ScoreSubmissionResponse;
import com.leaderboard.service.ScoreIngestionService;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * REST Controller for score submission endpoints.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/scores")
@RequiredArgsConstructor
@Validated
public class ScoreController {

    private final ScoreIngestionService scoreIngestionService;

    /**
     * Submit a new score.
     *
     * POST /api/v1/scores
     *
     * The score is queued for asynchronous processing.
     * Returns 202 Accepted with an event ID for tracking.
     */
    @PostMapping
    public ResponseEntity<ScoreSubmissionResponse> submitScore(
            @Valid @RequestBody ScoreSubmission submission) {

        log.debug("Received score submission for player: {}", submission.getPlayerId());

        ScoreSubmissionResponse response = scoreIngestionService.submitScore(submission);

        if (response.getStatus() == ScoreSubmissionResponse.SubmissionStatus.REJECTED) {
            return ResponseEntity.badRequest().body(response);
        }

        return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);
    }

    /**
     * Submit a score synchronously.
     * Waits for Kafka acknowledgment before returning.
     *
     * POST /api/v1/scores/sync
     */
    @PostMapping("/sync")
    public ResponseEntity<ScoreSubmissionResponse> submitScoreSync(
            @Valid @RequestBody ScoreSubmission submission) {

        log.debug("Received sync score submission for player: {}", submission.getPlayerId());

        try {
            ScoreSubmissionResponse response = scoreIngestionService.submitScoreSync(submission);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("Sync score submission failed for player: {}", submission.getPlayerId(), e);
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(ScoreSubmissionResponse.rejected("Score submission failed: " + e.getMessage()));
        }
    }
}
