package com.urlshortener.exception;

import org.springframework.http.HttpStatus;

public class UrlNotFoundException extends UrlShortenerException {
    public UrlNotFoundException(String shortCode) {
        super("URL not found: " + shortCode, "URL_NOT_FOUND", HttpStatus.NOT_FOUND);
    }
}
