package com.urlshortener.exception;

import org.springframework.http.HttpStatus;

public class RateLimitExceededException extends UrlShortenerException {
    public RateLimitExceededException() {
        super("Rate limit exceeded", "RATE_LIMITED", HttpStatus.TOO_MANY_REQUESTS);
    }
}
