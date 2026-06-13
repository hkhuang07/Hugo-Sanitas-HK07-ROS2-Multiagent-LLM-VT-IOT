package com.hk07.domain.agent.service;

import com.hk07.domain.agent.dto.AgentLogRequest;
import com.hk07.domain.agent.entity.AgentLogEntity;
import com.hk07.domain.agent.repository.AgentLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.stream.Collectors;

/**
 * Agent Log Service — Phase 09
 *
 * Receives decision logs from Python hk07-agent and:
 * 1. Validates and sanitizes input (truncates oversized context)
 * 2. Persists to agent_logs table
 * 3. Broadcasts to Vue Dashboard via WebSocket /topic/agent-events
 *
 * The @Async annotation ensures this never blocks the caller (Python REST call returns fast).
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class AgentLogService {

    private static final int MAX_CONTEXT_CHARS = 1000;
    private static final int MAX_DECISION_CHARS = 2000;

    private final AgentLogRepository agentLogRepository;
    private final SimpMessagingTemplate wsTemplate;

    @Async
    @Transactional
    public void recordDecision(AgentLogRequest req) {
        // Sanitize input sizes (prevent DB column overflow)
        String context = truncate(req.getInputContext(), MAX_CONTEXT_CHARS);
        String decision = truncate(req.getOutputDecision(), MAX_DECISION_CHARS);
        java.time.LocalDateTime triggeredAt = java.time.LocalDateTime.now();

        AgentLogEntity log = AgentLogEntity.builder()
                .agentType(req.getAgentType())
                .inputContext(context)
                .outputDecision(decision)
                .llmProvider(req.getLlmProvider())
                .latencyMs(req.getLatencyMs())
                .userId(req.getUserId())
                .triggeredAt(triggeredAt)
                .build();

        AgentLogEntity savedLog = agentLogRepository.save(log);

        // Broadcast to frontend immediately (no WebSocket ID needed — log is global)
        java.util.Map<String, Object> logPayload = new java.util.HashMap<>();
        logPayload.put("id", savedLog.getId().toString());
        logPayload.put("agentType", savedLog.getAgentType().name());
        logPayload.put("inputContext", context != null ? context : "");
        logPayload.put("outputDecision", decision);
        logPayload.put("llmProvider", savedLog.getLlmProvider() != null ? savedLog.getLlmProvider() : "UNKNOWN");
        logPayload.put("latencyMs", savedLog.getLatencyMs());
        logPayload.put("triggeredAt", triggeredAt.toString());
        logPayload.put("userId", savedLog.getUserId() != null ? savedLog.getUserId() : "");

        wsTemplate.convertAndSend("/topic/agent-events", logPayload);
        wsTemplate.convertAndSend("/topic/agent-logs", logPayload);

        this.log.info("[AGENT_LOG] {} | {}ms | {}", req.getAgentType(), req.getLatencyMs(),
                decision.length() > 60 ? decision.substring(0, 60) + "..." : decision);
    }

    @Transactional(readOnly = true)
    public Page<AgentLogEntity> getRecentLogs(int page, int size) {
        return agentLogRepository.findAllByOrderByTriggeredAtDesc(PageRequest.of(page, size));
    }

    @Transactional(readOnly = true)
    public Map<String, Long> getDecisionCounts() {
        return agentLogRepository.countByAgentType().stream()
                .collect(Collectors.toMap(
                    r -> r[0].toString(),
                    r -> (Long) r[1]
                ));
    }

    private String truncate(String s, int max) {
        if (s == null) return null;
        return s.length() > max ? s.substring(0, max) + "[TRUNCATED]" : s;
    }
}
