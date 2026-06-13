package com.hk07.domain.health.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

/**
 * DTO for reading and writing MedicalThresholdEntity via REST API.
 * Used by both GET (view current thresholds) and PUT (update thresholds).
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MedicalThresholdDto {

    private UUID id;
    private UUID userId;
    private String deviceId;

    // Heart Rate (BPM)
    private int hrMin;
    private int hrMax;

    // Blood Pressure (mmHg)
    private float systolicMax;
    private float diastolicMax;

    // SpO2 (%) & Temperature (°C)
    private float spo2Min;
    private float tempMax;

    // Feature flags
    private boolean strokeAlertEnabled;
    private boolean emergencyButtonEnabled;

    // Metadata
    private String label;
    private UUID configuredBy;
    private Instant updatedAt;
}
