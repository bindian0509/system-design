package com.ratelimiter.exception;

import com.ratelimiter.domain.RateLimitResult;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Global exception handler for REST endpoints.
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(RateLimitExceededException.class)
    public ResponseEntity<Map<String, Object>> handleRateLimitExceeded(RateLimitExceededException ex) {
        RateLimitResult result = ex.getResult();

        Map<String, Object> body = new HashMap<>();
        body.put("error", "Rate Limit Exceeded");
        body.put("code", "RATE_LIMITED");
        body.put("message", ex.getMessage());
        body.put("limit", result.limit());
        body.put("remaining", result.remainingRequests());
        body.put("retryAfter", result.retryAfterSeconds());
        body.put("resetTime", result.windowResetTime());

        if (result.violatedRuleId() != null) {
            body.put("violatedRule", result.violatedRuleId());
        }

        return ResponseEntity
            .status(HttpStatus.TOO_MANY_REQUESTS)
            .header("X-RateLimit-Limit", String.valueOf(result.limit()))
            .header("X-RateLimit-Remaining", "0")
            .header("X-RateLimit-Reset", String.valueOf(result.resetTimeEpochSeconds()))
            .header("Retry-After", String.valueOf(result.retryAfterSeconds()))
            .body(body);
    }

    @ExceptionHandler(RateLimiterUnavailableException.class)
    public ResponseEntity<Map<String, Object>> handleRateLimiterUnavailable(RateLimiterUnavailableException ex) {
        log.error("Rate limiter unavailable: {}", ex.getMessage());

        Map<String, Object> body = new HashMap<>();
        body.put("error", "Service Unavailable");
        body.put("code", "RATE_LIMITER_UNAVAILABLE");
        body.put("message", "Rate limiting service is temporarily unavailable");
        body.put("timestamp", Instant.now());

        return ResponseEntity
            .status(HttpStatus.SERVICE_UNAVAILABLE)
            .body(body);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidationErrors(MethodArgumentNotValidException ex) {
        Map<String, Object> body = new HashMap<>();
        body.put("error", "Validation Error");
        body.put("code", "INVALID_REQUEST");

        Map<String, String> fieldErrors = new HashMap<>();
        ex.getBindingResult().getFieldErrors().forEach(error ->
            fieldErrors.put(error.getField(), error.getDefaultMessage()));
        body.put("errors", fieldErrors);

        return ResponseEntity
            .status(HttpStatus.BAD_REQUEST)
            .body(body);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArgument(IllegalArgumentException ex) {
        Map<String, Object> body = new HashMap<>();
        body.put("error", "Bad Request");
        body.put("code", "INVALID_ARGUMENT");
        body.put("message", ex.getMessage());

        return ResponseEntity
            .status(HttpStatus.BAD_REQUEST)
            .body(body);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleGenericException(Exception ex) {
        log.error("Unexpected error: {}", ex.getMessage(), ex);

        Map<String, Object> body = new HashMap<>();
        body.put("error", "Internal Server Error");
        body.put("code", "INTERNAL_ERROR");
        body.put("message", "An unexpected error occurred");
        body.put("timestamp", Instant.now());

        return ResponseEntity
            .status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(body);
    }
}
