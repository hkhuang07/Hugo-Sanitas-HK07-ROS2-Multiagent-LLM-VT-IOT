package com.hk07.domain.user.dto;

import lombok.Builder;
import lombok.Data;

import java.util.UUID;

@Data @Builder
public class WristbandConfigDto {
    private UUID id;
    private String deviceId;
    private String mqttTopic;
    private int heartRateThresholdMin;
    private int heartRateThresholdMax;
    private float bloodPressureSystolicMax;
    private float spo2Min;
    private boolean strokeAlertEnabled;
}
