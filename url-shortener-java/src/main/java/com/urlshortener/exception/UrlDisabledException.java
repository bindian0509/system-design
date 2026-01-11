package com.urlshortener.exception;

import org.springframework.http.HttpStatus;

public class UrlDisabledException extends UrlShortenerException {
    public UrlDisabledException(String shortCode) {
        super("URL is disabled: " + shortCode, "URL_DISABLED", HttpStatus.FORBIDDEN);
    }
}
