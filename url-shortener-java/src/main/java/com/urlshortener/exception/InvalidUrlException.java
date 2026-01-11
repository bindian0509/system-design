package com.urlshortener.exception;

import org.springframework.http.HttpStatus;

public class InvalidUrlException extends UrlShortenerException {
    public InvalidUrlException(String message) {
        super(message, "INVALID_URL", HttpStatus.BAD_REQUEST);
    }
}
