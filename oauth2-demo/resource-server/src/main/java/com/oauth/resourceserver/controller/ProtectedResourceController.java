package com.oauth.resourceserver.controller;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
@Slf4j
public class ProtectedResourceController {

    /**
     * Public endpoint - no authentication required
     */
    @GetMapping("/public/health")
    public ResponseEntity<Map<String, Object>> publicHealth() {
        Map<String, Object> response = new HashMap<>();
        response.put("status", "UP");
        response.put("message", "Resource Server is running");
        response.put("timestamp", Instant.now().toString());
        response.put("authenticated", false);
        return ResponseEntity.ok(response);
    }

    /**
     * Public endpoint - information about the API
     */
    @GetMapping("/public/info")
    public ResponseEntity<Map<String, Object>> publicInfo() {
        Map<String, Object> response = new HashMap<>();
        response.put("name", "OAuth 2.0 Resource Server Demo");
        response.put("version", "1.0.0");
        response.put("description", "A demo resource server protected by OAuth 2.0");
        response.put("endpoints", Map.of(
                "/api/public/**", "No authentication required",
                "/api/protected", "Requires valid access token",
                "/api/user", "Requires valid access token, returns user info",
                "/api/admin/**", "Requires ADMIN role"
        ));
        return ResponseEntity.ok(response);
    }

    /**
     * Protected endpoint - requires any valid access token
     */
    @GetMapping("/protected")
    public ResponseEntity<Map<String, Object>> protectedResource(@AuthenticationPrincipal Jwt jwt) {
        log.info("Protected resource accessed by: {}", jwt.getSubject());

        Map<String, Object> response = new HashMap<>();
        response.put("message", "You have successfully accessed a protected resource!");
        response.put("timestamp", Instant.now().toString());
        response.put("authenticated", true);
        response.put("subject", jwt.getSubject());
        return ResponseEntity.ok(response);
    }

    /**
     * User info endpoint - returns details from the JWT token
     */
    @GetMapping("/user")
    public ResponseEntity<Map<String, Object>> userInfo(@AuthenticationPrincipal Jwt jwt) {
        log.info("User info requested by: {}", jwt.getSubject());

        Map<String, Object> response = new HashMap<>();
        response.put("subject", jwt.getSubject());
        response.put("username", jwt.getClaimAsString("username"));
        response.put("authorities", jwt.getClaimAsStringList("authorities"));
        response.put("scopes", jwt.getClaimAsString("scope"));
        response.put("issuer", jwt.getIssuer().toString());
        response.put("issuedAt", jwt.getIssuedAt().toString());
        response.put("expiresAt", jwt.getExpiresAt().toString());
        response.put("tokenId", jwt.getId());
        return ResponseEntity.ok(response);
    }

    /**
     * Endpoint requiring 'read' scope
     */
    @GetMapping("/data")
    @PreAuthorize("hasAuthority('SCOPE_read')")
    public ResponseEntity<Map<String, Object>> readData(@AuthenticationPrincipal Jwt jwt) {
        log.info("Read data requested by: {}", jwt.getSubject());

        Map<String, Object> response = new HashMap<>();
        response.put("message", "Here is some data you can read!");
        response.put("data", Map.of(
                "id", 1,
                "name", "Sample Resource",
                "description", "This is a sample resource that requires 'read' scope",
                "createdAt", Instant.now().minusSeconds(86400).toString()
        ));
        response.put("requestedBy", jwt.getClaimAsString("username"));
        return ResponseEntity.ok(response);
    }

    /**
     * Endpoint requiring 'write' scope
     */
    @GetMapping("/data/write-check")
    @PreAuthorize("hasAuthority('SCOPE_write')")
    public ResponseEntity<Map<String, Object>> checkWriteAccess(@AuthenticationPrincipal Jwt jwt) {
        log.info("Write access check by: {}", jwt.getSubject());

        Map<String, Object> response = new HashMap<>();
        response.put("message", "You have write access!");
        response.put("canWrite", true);
        response.put("requestedBy", jwt.getClaimAsString("username"));
        return ResponseEntity.ok(response);
    }

    /**
     * Admin-only endpoint - requires ADMIN role
     */
    @GetMapping("/admin/dashboard")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Object>> adminDashboard(@AuthenticationPrincipal Jwt jwt) {
        log.info("Admin dashboard accessed by: {}", jwt.getSubject());

        Map<String, Object> response = new HashMap<>();
        response.put("message", "Welcome to the Admin Dashboard!");
        response.put("adminFeatures", Map.of(
                "userManagement", "enabled",
                "systemConfig", "enabled",
                "auditLogs", "enabled",
                "analytics", "enabled"
        ));
        response.put("requestedBy", jwt.getClaimAsString("username"));
        response.put("authorities", jwt.getClaimAsStringList("authorities"));
        return ResponseEntity.ok(response);
    }

    /**
     * Admin endpoint requiring both ADMIN role and 'admin' scope
     */
    @GetMapping("/admin/settings")
    @PreAuthorize("hasRole('ADMIN') and hasAuthority('SCOPE_admin')")
    public ResponseEntity<Map<String, Object>> adminSettings(@AuthenticationPrincipal Jwt jwt) {
        log.info("Admin settings accessed by: {}", jwt.getSubject());

        Map<String, Object> response = new HashMap<>();
        response.put("message", "Admin settings - requires ADMIN role and admin scope");
        response.put("settings", Map.of(
                "maxUsers", 1000,
                "sessionTimeout", "30 minutes",
                "maintenanceMode", false
        ));
        return ResponseEntity.ok(response);
    }
}
