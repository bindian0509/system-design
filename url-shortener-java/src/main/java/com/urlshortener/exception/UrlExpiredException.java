package com.urlshortener.exception;

import org.springframework.http.HttpStatus;

public class UrlExpiredException extends UrlShortenerException {
    public UrlExpiredException(String shortCode) {
        super("URL has expired: " + shortCode, "URL_EXPIRED", HttpStatus.GONE);
    }
}
