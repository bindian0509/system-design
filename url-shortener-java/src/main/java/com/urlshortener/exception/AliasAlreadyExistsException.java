package com.urlshortener.exception;

import org.springframework.http.HttpStatus;

public class AliasAlreadyExistsException extends UrlShortenerException {
    public AliasAlreadyExistsException(String alias) {
        super("Custom alias already taken: " + alias, "ALIAS_TAKEN", HttpStatus.CONFLICT);
    }
}
