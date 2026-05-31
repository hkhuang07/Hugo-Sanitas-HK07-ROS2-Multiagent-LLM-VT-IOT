package com.hk07.domain.safety.entity;

import com.hk07.common.enums.AlertLevel;
import com.hk07.common.enums.SafetyTrigger;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * SafetyAlert entity — records every Subsumption Architecture activation.
 * Key field: responseTimeMs — must be < 5ms for system integrity certification.
 */
@Entity
@Table(name = "safety_alerts", indexes = {
    @Index(name = "idx_safety_time", columnList = "detected_at DESC")
})
@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor
public class SafetyAlertEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20, columnDefinition = "VARCHAR(20)")
    private AlertLevel level;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30, columnDefinition = "VARCHAR(30)")
    private SafetyTrigger triggerType;

    private float distanceMeters;       // Distance to obstacle at trigger time

    @Column(columnDefinition = "TEXT")
    private String message;

    private boolean subsumptionActivated;

    /** Must be < 5ms per PRD §2.2 */
    private float responseTimeMs;

    @CreationTimestamp
    private LocalDateTime detectedAt;
}
