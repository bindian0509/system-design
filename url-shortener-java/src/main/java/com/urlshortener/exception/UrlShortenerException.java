package com.urlshortener.exception;

import org.springframework.http.HttpStatus;

/**
 * Base exception for URL shortener
 */
public abstract class UrlShortenerException extends RuntimeException {

    private final String code;
    private final HttpStatus status;

    protected UrlShortenerException(String message, String code, HttpStatus status) {
        super(message);
        this.code = code;
        this.status = status;
    }

    public String getCode() {
        return code;
    }

    public HttpStatus getStatus() {
        return status;
    }
}
