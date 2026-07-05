package com.hk07.domain.health.entity;

import com.hk07.common.enums.AlertLevel;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * HealthRecord entity — persisted output after Medical Agent analysis.
 *
 * Raw VitalSignDto flows in via MQTT → Medical Agent processes → HealthRecord saved.
 * Includes AI-generated analysis text and computed AlertLevel.
 *
 * Partitioned by recorded_at for efficient time-series queries.
 * (Flyway migration will add partitioning; JPA handles the entity mapping)
 */
@Entity
@Table(name = "health_records", indexes = {
    @Index(name = "idx_hr_user_time", columnList = "user_id, recorded_at DESC")
})
@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor
public class HealthRecordEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    // ─── Raw vitals (denormalized for fast query; no JOIN needed) ────────────
    private Integer heartRate;
    private Float systolic;
    private Float diastolic;
    private Float bodyTemperature;
    private Float spo2;
    private String deviceId;

    // ─── AI Analysis output ──────────────────────────────────────────────────
    @Column(columnDefinition = "TEXT")
    private String agentAnalysis;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20, columnDefinition = "VARCHAR(20)")
    @Builder.Default
    private AlertLevel alertLevel = AlertLevel.NORMAL;

    @CreationTimestamp
    private LocalDateTime recordedAt;
}
