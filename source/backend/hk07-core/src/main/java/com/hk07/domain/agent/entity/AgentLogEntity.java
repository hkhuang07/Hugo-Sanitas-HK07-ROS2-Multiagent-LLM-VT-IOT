package com.hk07.domain.agent.entity;

import com.hk07.common.enums.AgentType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * AgentLog — persists every decision made by an AI agent.
 * Used for audit trail, performance monitoring (latencyMs), and dashboard replay.
 *
 * High-frequency insert: only WARNING+ decisions are persisted to protect
 * PostgreSQL under high sensor load (same strategy as HealthRecord).
 */
@Entity
@Table(name = "agent_logs", indexes = {
    @Index(name = "idx_agent_logs_type_time", columnList = "agent_type, triggered_at DESC")
})
@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor
public class AgentLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20, columnDefinition = "VARCHAR(20)")
    private AgentType agentType;

    @Column(columnDefinition = "TEXT")
    private String inputContext;    // Sensor data or user message that triggered this

    @Column(columnDefinition = "TEXT")
    private String outputDecision;  // Agent response / decision text

    @Column(length = 20)
    private String llmProvider;     // GROQ | GEMINI | MOCK | THRESHOLD

    private int latencyMs;          // End-to-end latency of this decision

    @CreationTimestamp
    private LocalDateTime triggeredAt;
}
