package com.hk07.domain.safety.controller;

import com.hk07.common.dto.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/safety")
@RequiredArgsConstructor
public class SafetyController {

    @GetMapping("/subsumption/status")
    public ResponseEntity<ApiResponse<java.util.Map<String, Object>>> subsumptionStatus() {
        return ResponseEntity.ok(ApiResponse.ok(java.util.Map.of(
                "visionLive", true,
                "threatLevel", "SAFE",
                "minDistanceM", 3.0
        )));
    }
}
