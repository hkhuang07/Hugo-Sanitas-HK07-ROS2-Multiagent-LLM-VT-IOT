package com.hk07.domain.health.entity;

import com.hk07.domain.user.entity.UserEntity;
import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.UUID;

/**
 * MedicalThresholdEntity — [HẠNCHẾ-#9 FIX]
 *
 * Replaces hardcoded threshold constants in HealthService with per-patient,
 * per-device configurable limits stored in the database.
 *
 * Configured by: Owner (self) or Medic (clinical override).
 * Queried by: HealthService.computeAlertLevel() on every vital sign.
 *
 * Design notes:
 * - Separate from WristbandConfigEntity to support future multi-device profiles.
 * - Lazy-fetched User join to avoid N+1 on bulk threshold lookups.
 * - Updated_at is auto-managed by MariaDB ON UPDATE CURRENT_TIMESTAMP.
 */
@Entity
@Table(name = "medical_thresholds")
@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor
public class MedicalThresholdEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private UserEntity user;

    @Column(nullable = false, length = 100)
    private String deviceId;

    // ── Heart Rate ─────────────────────────────────────────────────────────
    @Column(nullable = false)
    @Builder.Default private int hrMin = 50;

    @Column(nullable = false)
    @Builder.Default private int hrMax = 120;

    // ── Blood Pressure ─────────────────────────────────────────────────────
    @Column(nullable = false)
    @Builder.Default private float systolicMax = 140.0f;

    @Column(nullable = false)
    @Builder.Default private float diastolicMax = 90.0f;

    // ── SpO2 & Temperature ─────────────────────────────────────────────────
    @Column(name = "spo2_min", nullable = false)
    @Builder.Default private float spo2Min = 92.0f;

    @Column(nullable = false)
    @Builder.Default private float tempMax = 38.5f;

    // ── Feature Flags ──────────────────────────────────────────────────────
    @Column(nullable = false)
    @Builder.Default private boolean strokeAlertEnabled = true;

    @Column(nullable = false)
    @Builder.Default private boolean emergencyButtonEnabled = true;

    // ── Metadata ───────────────────────────────────────────────────────────
    /** Human-readable profile label, e.g. "Post-cardiac surgery" */
    @Column(length = 100)
    private String label;

    /** UUID of the Medic/Owner who last configured this profile */
    @Column(name = "configured_by")
    private UUID configuredBy;

    @Column(nullable = false, updatable = false)
    @Builder.Default private Instant createdAt = Instant.now();

    @Column(nullable = false)
    @Builder.Default private Instant updatedAt = Instant.now();

    @PreUpdate
    void onUpdate() { this.updatedAt = Instant.now(); }
}
