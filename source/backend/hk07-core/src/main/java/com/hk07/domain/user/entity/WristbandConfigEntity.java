package com.hk07.domain.user.entity;

import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

/**
 * Wristband device configuration per owner.
 * Stores MQTT topic, BLE device ID, and medical alert thresholds.
 */
@Entity
@Table(name = "wristband_configs")
@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor
public class WristbandConfigEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false, unique = true)
    private UserEntity user;

    /** BLE MAC address or UUID of the physical wristband */
    @Column(nullable = false, length = 100)
    private String deviceId;

    /** MQTT topic this device publishes vital signs to */
    @Column(nullable = false, length = 200)
    private String mqttTopic;

    @Builder.Default private int heartRateThresholdMin = 50;
    @Builder.Default private int heartRateThresholdMax = 120;
    @Builder.Default private float bloodPressureSystolicMax = 140.0f;
    @Column(name = "spo2_min")
    @Builder.Default private float spo2Min = 92.0f;
    @Builder.Default private boolean strokeAlertEnabled = true;
}
