package com.hk07.domain.audit.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.UUID;

/**
 * AuditLogEntity — [HẠNCHẾ-#11 FIX]
 *
 * Immutable medical audit trail record. Logged on every emergency action.
 *
 * Anti-tampering: integrityHash = SHA-256(actorId | actionType | actionPayload | executedAt)
 * Any post-write modification to action_payload or executed_at will invalidate the hash,
 * detectable by the AuditService.verifyIntegrity() method.
 *
 * Design: No @Setter — fields set only via @Builder to enforce immutability after creation.
 */
@Entity
@Table(name = "audit_logs")
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AuditLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    // ── Actor ──────────────────────────────────────────────────────────────
    @Column(name = "actor_id", nullable = false)
    private UUID actorId;

    @Column(name = "actor_role", nullable = false, length = 30)
    private String actorRole;

    // ── Action ─────────────────────────────────────────────────────────────
    @Column(name = "action_type", nullable = false, length = 50)
    private String actionType;

    @Column(name = "target_device", length = 100)
    private String targetDevice;

    @Column(name = "action_payload", columnDefinition = "TEXT")
    private String actionPayload;

    // ── Outcome ────────────────────────────────────────────────────────────
    @Column(nullable = false, length = 20)
    @Builder.Default
    private String outcome = "SUCCESS";

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    // ── Integrity ──────────────────────────────────────────────────────────
    /** SHA-256(actorId + "|" + actionType + "|" + actionPayload + "|" + executedAt.toEpochMilli()) */
    @Column(name = "integrity_hash", nullable = false, length = 64)
    private String integrityHash;

    // ── Metadata ───────────────────────────────────────────────────────────
    @Column(name = "ip_address", length = 45)
    private String ipAddress;

    @Column(name = "executed_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant executedAt = Instant.now();
}
