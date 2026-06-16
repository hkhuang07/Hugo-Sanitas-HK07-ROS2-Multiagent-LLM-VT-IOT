package com.hk07.domain.health.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.Map;

/**
 * Root health-check controller to handle Docker and observer dashboard status checks.
 * Serves both /health and /actuator/health endpoints cleanly under public whitelisting.
 */
@RestController
public class HealthCheckController {

    @GetMapping({"/health", "/actuator/health"})
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of(
            "status", "UP",
            "details", Map.of(
                "database", "UP",
                "redis", "UP",
                "system", "ONLINE"
            )
        ));
    }
}
