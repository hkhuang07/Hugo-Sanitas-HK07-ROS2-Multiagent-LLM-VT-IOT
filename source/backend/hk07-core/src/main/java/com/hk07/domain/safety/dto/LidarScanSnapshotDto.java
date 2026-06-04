package com.hk07.domain.safety.dto;

import lombok.Builder;
import lombok.Data;

/**
 * Latest LiDAR scan normalized for the Safety dashboard (360 bearings).
 */
@Data
@Builder
public class LidarScanSnapshotDto {
    private float[] ranges360;
    private float minDistanceM;
    private int closestAngleDeg;
    private long timestampMs;
    private double scanHz;
    /** SAFE | CAUTION | WARNING | CRITICAL — matches SafetyAgent thresholds */
    private String threatLevel;
    private String baymaxHint;
    private boolean live;
    private int sectorCount;
}
