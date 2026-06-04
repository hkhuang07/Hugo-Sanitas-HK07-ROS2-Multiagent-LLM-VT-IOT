package com.hk07.domain.safety.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.safety.dto.LidarScanSnapshotDto;
import com.hk07.domain.safety.service.SafetyTelemetryService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/safety")
@RequiredArgsConstructor
public class SafetyController {

    private final SafetyTelemetryService safetyTelemetryService;

    @GetMapping("/lidar/snapshot")
    public ResponseEntity<ApiResponse<LidarScanSnapshotDto>> lidarSnapshot() {
        return ResponseEntity.ok(ApiResponse.ok(safetyTelemetryService.getSnapshot()));
    }

    @GetMapping("/subsumption/status")
    public ResponseEntity<ApiResponse<java.util.Map<String, Object>>> subsumptionStatus() {
        var snap = safetyTelemetryService.getSnapshot();
        return ResponseEntity.ok(ApiResponse.ok(java.util.Map.of(
                "lidarLive", snap.isLive(),
                "threatLevel", snap.getThreatLevel(),
                "minDistanceM", snap.getMinDistanceM()
        )));
    }
}
