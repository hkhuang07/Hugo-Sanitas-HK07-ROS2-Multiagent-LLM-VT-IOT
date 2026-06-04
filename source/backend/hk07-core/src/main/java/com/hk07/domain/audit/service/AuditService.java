package com.hk07.domain.audit.service;

import com.hk07.domain.audit.entity.AuditLogEntity;
import com.hk07.domain.audit.repository.AuditLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.UUID;

/**
 * AuditService — [HẠNCHẾ-#11 FIX]
 *
 * Records every emergency command into the audit_logs table with an
 * SHA-256 integrity hash for medical record anti-tampering.
 *
 * Hash input: actorId | actionType | actionPayload | executedAt(epochMs)
 * Any post-write modification to these fields will cause verifyIntegrity()
 * to return false, flagging potential record tampering.
 *
 * @Async: audit logging runs on a Virtual Thread — never blocks the
 * critical safety command execution path.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class AuditService {

    private final AuditLogRepository auditLogRepository;

    /**
     * Record an emergency/critical command in the audit trail.
     * Called from RobotCommandService for HOLD, RESUME, SHUTDOWN, INHIBIT.
     * Called from MedicalThresholdController for THRESHOLD_UPDATE.
     *
     * @param actorId       UUID of the user issuing the command
     * @param actorRole     Role string at time of action
     * @param actionType    One of the allowed action type constants
     * @param targetDevice  Device ID affected (null if system-wide)
     * @param payload       JSON string of command parameters
     * @param outcome       "SUCCESS" | "FAILED" | "DENIED"
     * @param ipAddress     Client IP for audit trail
     */
    @Async
    public void record(UUID actorId, String actorRole, String actionType,
                       String targetDevice, String payload, String outcome, String ipAddress) {
        try {
            if (actorId == null) {
                actorId = UUID.fromString("00000000-0000-0000-0000-000000000000");
            }
            if (actorRole == null || actorRole.isEmpty()) {
                actorRole = "SYSTEM_AGENT";
            }
            if (actionType == null || actionType.isEmpty()) {
                actionType = "UNKNOWN";
            }
            if (outcome == null || outcome.isEmpty()) {
                outcome = "SUCCESS";
            }

            Instant now = Instant.now();
            String hash = computeHash(actorId, actionType, payload, now);

            AuditLogEntity log_entry = AuditLogEntity.builder()
                    .actorId(actorId)
                    .actorRole(actorRole)
                    .actionType(actionType)
                    .targetDevice(targetDevice)
                    .actionPayload(payload)
                    .outcome(outcome)
                    .integrityHash(hash)
                    .ipAddress(ipAddress)
                    .executedAt(now)
                    .build();

            auditLogRepository.save(log_entry);
            log.info("[AUDIT] {} | actor={} role={} device={} outcome={}",
                    actionType, actorId, actorRole, targetDevice, outcome);
        } catch (Exception e) {
            // Audit failure must NEVER propagate to the calling command
            log.error("[AUDIT_ERROR] Failed to write audit log: {}", e.getMessage());
        }
    }

    /**
     * Verify the integrity of an existing audit record.
     * Returns false if the record has been tampered with after creation.
     */
    public boolean verifyIntegrity(AuditLogEntity entry) {
        try {
            String expected = computeHash(
                entry.getActorId(), entry.getActionType(),
                entry.getActionPayload(), entry.getExecutedAt()
            );
            return expected.equals(entry.getIntegrityHash());
        } catch (Exception e) {
            log.error("[AUDIT_VERIFY_ERROR] {}", e.getMessage());
            return false;
        }
    }

    /**
     * SHA-256 hash of: actorId + "|" + actionType + "|" + payload + "|" + epochMs
     */
    private String computeHash(UUID actorId, String actionType, String payload, Instant ts) {
        try {
            String raw = String.join("|",
                actorId != null ? actorId.toString() : "system",
                actionType,
                payload != null ? payload : "",
                String.valueOf(ts.toEpochMilli())
            );
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hashBytes = digest.digest(raw.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hashBytes);
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }

    // ── Action Type Constants ─────────────────────────────────────────────
    public static final String INHIBIT          = "INHIBIT";
    public static final String INHIBIT_CLEAR    = "INHIBIT_CLEAR";
    public static final String SOS_DISPATCH     = "SOS_DISPATCH";
    public static final String SAFE_HOLD        = "SAFE_HOLD";
    public static final String RESUME           = "RESUME";
    public static final String SHUTDOWN         = "SHUTDOWN";
    public static final String THRESHOLD_UPDATE = "THRESHOLD_UPDATE";
    public static final String EMERGENCY_BUTTON = "EMERGENCY_BUTTON";
}
