package com.urlshortener.domain.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.validator.constraints.URL;

import java.util.List;

/**
 * Request DTO for creating a new shortened URL
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CreateUrlRequest {

    @NotBlank(message = "URL is required")
    @URL(message = "Invalid URL format")
    @Size(max = 4096, message = "URL too long")
    private String url;

    @Size(min = 4, max = 50, message = "Custom alias must be 4-50 characters")
    private String customAlias;

    private Long ttlSeconds;

    @Size(max = 500, message = "Title too long")
    private String title;

    @Size(max = 2000, message = "Description too long")
    private String description;

    @Size(max = 10, message = "Maximum 10 tags allowed")
    private List<String> tags;
}
