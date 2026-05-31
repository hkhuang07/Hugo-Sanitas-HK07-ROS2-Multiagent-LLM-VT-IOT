package com.hk07.domain.agent.dto;

import com.hk07.common.enums.AgentType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * AgentLogRequest — payload sent by Python hk07-agent via REST POST.
 *
 * Python agents call:
 *   POST /api/v1/agents/log
 *   Authorization: Bearer <internal-service-token>
 *
 * No userId here — agent logs are system-level, not per-user.
 * Alert-level analysis is deduced from outputDecision by the frontend.
 */
@Data
public class AgentLogRequest {

    @NotNull
    private AgentType agentType;

    private String inputContext;     // Sensor payload or user message (truncated at 1000 chars)

    @NotBlank
    private String outputDecision;   // Agent's decision or response (truncated at 2000 chars)

    private String llmProvider;      // GROQ | GEMINI | THRESHOLD | MOCK

    private int latencyMs;           // End-to-end latency measured by Python agent
}
