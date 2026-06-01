package com.hk07.domain.health.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.health.entity.HealthRecordEntity;
import com.hk07.domain.health.service.HealthService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/health")
@RequiredArgsConstructor
public class HealthController {

    private final HealthService healthService;

    @GetMapping("/vitals/latest")
    public ResponseEntity<ApiResponse<HealthRecordEntity>> getLatest(Authentication auth) {
        UUID userId = UUID.fromString(auth.getName());
        return healthService.getLatestVital(userId)
                .map(r -> ResponseEntity.ok(ApiResponse.ok(r)))
                .orElse(ResponseEntity.ok(ApiResponse.ok("No vitals recorded yet", null)));
    }

    @GetMapping("/alerts/active")
    public ResponseEntity<ApiResponse<List<HealthRecordEntity>>> getAlerts(Authentication auth) {
        UUID userId = UUID.fromString(auth.getName());
        return ResponseEntity.ok(ApiResponse.ok(healthService.getActiveAlerts(userId)));
    }

    @GetMapping("/history/hourly")
    public ResponseEntity<ApiResponse<List<com.hk07.domain.health.dto.HourlySummaryDto>>> getHourlyHistory(
            Authentication auth,
            @RequestParam(value = "hours", defaultValue = "24") int hours) {
        UUID userId = UUID.fromString(auth.getName());
        return ResponseEntity.ok(ApiResponse.ok(healthService.getHourlySummary(userId, hours)));
    }

    /**
     * [HẠNCHẾ-#4 FIX] Endpoint for frontend to push offline cached vitals when network restores.
     * The frontend's IndexedDB stores vitals if the WebSocket connection is dropped.
     */
    @PostMapping("/sync-offline")
    public ResponseEntity<ApiResponse<String>> syncOfflineVitals(
            Authentication auth,
            @RequestBody List<com.hk07.domain.health.dto.VitalSignDto> offlineRecords) {
        if (offlineRecords == null || offlineRecords.isEmpty()) {
            return ResponseEntity.ok(ApiResponse.ok("No records to sync"));
        }
        UUID userId = UUID.fromString(auth.getName());
        // Forward all records to HealthService (which uses Virtual Threads and Batching)
        offlineRecords.forEach(healthService::processVitalSign);
        return ResponseEntity.ok(ApiResponse.ok("Synced " + offlineRecords.size() + " offline records"));
    }
}
