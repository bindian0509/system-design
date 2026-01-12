package com.leaderboard.exception;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import lombok.extern.slf4j.Slf4j;

/**
 * Global exception handler for REST endpoints.
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(PlayerNotFoundException.class)
    public ResponseEntity<ErrorResponse> handlePlayerNotFound(PlayerNotFoundException ex) {
        log.warn("Player not found: {}", ex.getMessage());

        ErrorResponse error = new ErrorResponse(
            "PLAYER_NOT_FOUND",
            ex.getMessage(),
            HttpStatus.NOT_FOUND.value()
        );

        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
    }

    @ExceptionHandler(LeaderboardException.class)
    public ResponseEntity<ErrorResponse> handleLeaderboardException(LeaderboardException ex) {
        log.error("Leaderboard error: {}", ex.getMessage(), ex);

        ErrorResponse error = new ErrorResponse(
            "LEADERBOARD_ERROR",
            ex.getMessage(),
            HttpStatus.INTERNAL_SERVER_ERROR.value()
        );

        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ValidationErrorResponse> handleValidationErrors(
            MethodArgumentNotValidException ex) {

        Map<String, String> errors = new HashMap<>();
        ex.getBindingResult().getAllErrors().forEach((error) -> {
            String fieldName = ((FieldError) error).getField();
            String errorMessage = error.getDefaultMessage();
            errors.put(fieldName, errorMessage);
        });

        ValidationErrorResponse response = new ValidationErrorResponse(
            "VALIDATION_ERROR",
            "Request validation failed",
            HttpStatus.BAD_REQUEST.value(),
            errors
        );

        return ResponseEntity.badRequest().body(response);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorResponse> handleIllegalArgument(IllegalArgumentException ex) {
        log.warn("Invalid argument: {}", ex.getMessage());

        ErrorResponse error = new ErrorResponse(
            "INVALID_ARGUMENT",
            ex.getMessage(),
            HttpStatus.BAD_REQUEST.value()
        );

        return ResponseEntity.badRequest().body(error);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGenericException(Exception ex) {
        log.error("Unexpected error", ex);

        ErrorResponse error = new ErrorResponse(
            "INTERNAL_ERROR",
            "An unexpected error occurred",
            HttpStatus.INTERNAL_SERVER_ERROR.value()
        );

        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
    }

    /**
     * Standard error response.
     */
    public record ErrorResponse(
        String code,
        String message,
        int status,
        Instant timestamp
    ) {
        public ErrorResponse(String code, String message, int status) {
            this(code, message, status, Instant.now());
        }
    }

    /**
     * Validation error response with field-level errors.
     */
    public record ValidationErrorResponse(
        String code,
        String message,
        int status,
        Map<String, String> errors,
        Instant timestamp
    ) {
        public ValidationErrorResponse(String code, String message, int status, Map<String, String> errors) {
            this(code, message, status, errors, Instant.now());
        }
    }
}
