package com.hk07.domain.health.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.health.dto.HourlySummaryDto;
import com.hk07.domain.health.entity.HealthRecordEntity;
import com.hk07.domain.health.service.HealthService;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
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

    /**
     * Hourly summary — sliding window from now back N hours.
     * Supports ?hours=6|12|24|48|72
     * Max allowed: 168 hours (7 days) — server enforced.
     */
    @GetMapping("/history/hourly")
    public ResponseEntity<ApiResponse<List<HourlySummaryDto>>> getHourlyHistory(
            Authentication auth,
            @RequestParam(value = "hours", defaultValue = "24") int hours) {
        UUID userId = UUID.fromString(auth.getName());
        int cappedHours = Math.min(hours, 168); // Max 7 days
        return ResponseEntity.ok(ApiResponse.ok(healthService.getHourlySummary(userId, cappedHours)));
    }

    /**
     * Custom date-range hourly summary.
     * Accepts ISO8601 datetime strings: ?fromDate=2026-06-01T00:00:00&toDate=2026-06-05T23:59:59
     * Max window: 90 days (enforced in HealthService).
     * Enables the frontend custom date picker to query arbitrary historical windows.
     */
    @GetMapping("/history/range")
    public ResponseEntity<ApiResponse<List<HourlySummaryDto>>> getHistoryByRange(
            Authentication auth,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime fromDate,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime toDate) {
        UUID userId = UUID.fromString(auth.getName());
        if (fromDate.isAfter(toDate)) {
            return ResponseEntity.badRequest()
                    .body(ApiResponse.error("fromDate must be before toDate"));
        }
        return ResponseEntity.ok(ApiResponse.ok(
                healthService.getHourlySummaryByRange(userId, fromDate, toDate)));
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
        offlineRecords.forEach(healthService::processVitalSign);
        return ResponseEntity.ok(ApiResponse.ok("Synced " + offlineRecords.size() + " offline records"));
    }
}

