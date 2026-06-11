package com.hk07.domain.health.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * VitalSignDto — Raw vital signs payload from MQTT wristband topic.
 * Data ingested at up to 60Hz from BLE wristband gateway.
 *
 * Not persisted directly — Medical Agent processes this first,
 * then a HealthRecord (with AI analysis) is saved to PostgreSQL.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VitalSignDto {

    /** MAC address or BLE UUID of the source wristband device */
    private String deviceId;

    /** Heart rate in beats-per-minute */
    private int heartRate;

    /** Systolic blood pressure in mmHg */
    private float systolic;

    /** Diastolic blood pressure in mmHg */
    private float diastolic;

    /** Body temperature in Celsius */
    private float bodyTemperature;

    /** Blood oxygen saturation (0-100%) */
    private float spo2;

    /** Unix epoch timestamp in milliseconds when wristband recorded this reading */
    private long epochTimestampMs;

    /** Hormone concentrations calculated by sensor fusion */
    private java.util.Map<String, Object> hormones;
}
