package com.hk07.domain.agent.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.agent.dto.AgentLogRequest;
import com.hk07.domain.agent.entity.AgentLogEntity;
import com.hk07.domain.agent.service.AgentLogService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Agent Log Controller — Phase 09
 *
 * Two concerns:
 * 1. POST /api/v1/agents/log — called by Python hk07-agent (internal service)
 *    Accepts agent decision logs and broadcasts them via WebSocket.
 *
 * 2. GET  /api/v1/agents/logs — called by Vue Dashboard
 *    Returns paginated log history for AgentsView.vue.
 *
 * Security: POST endpoint requires a valid JWT (internal service token).
 * The Python agent authenticates using the default owner JWT.
 */
@RestController
@RequestMapping("/api/v1/agents")
@RequiredArgsConstructor
public class AgentLogController {

    private final AgentLogService agentLogService;

    /** Called by Python hk07-agent to record a decision */
    @PostMapping("/log")
    public ResponseEntity<ApiResponse<Void>> recordLog(@Valid @RequestBody AgentLogRequest req) {
        agentLogService.recordDecision(req);
        return ResponseEntity.accepted().body(ApiResponse.ok("Agent decision logged", null));
    }

    /** Paginated log history for dashboard */
    @GetMapping("/logs")
    public ResponseEntity<ApiResponse<Page<AgentLogEntity>>> getLogs(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size) {
        // Hard cap size at 50 to prevent memory overload
        int cappedSize = Math.min(size, 50);
        return ResponseEntity.ok(ApiResponse.ok(agentLogService.getRecentLogs(page, cappedSize)));
    }

    /** Decision count stats per agent (for AgentsView.vue metrics panel) */
    @GetMapping("/stats")
    public ResponseEntity<ApiResponse<Map<String, Long>>> getStats() {
        return ResponseEntity.ok(ApiResponse.ok(agentLogService.getDecisionCounts()));
    }

    private final org.springframework.web.reactive.function.client.WebClient pythonAgentClient = 
            org.springframework.web.reactive.function.client.WebClient.builder().baseUrl("http://127.0.0.1:8889").build();

    /** Forward empathetic text interaction to Python agent engine */
    @PostMapping("/empathetic/interact")
    @SuppressWarnings("unchecked")
    public ResponseEntity<ApiResponse<Map<String, String>>> interact(@RequestBody Map<String, String> body) {
        try {
            Map<String, String> response = pythonAgentClient.post()
                    .uri("/agents/empathetic/interact")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(map -> Map.of("response", (String) map.get("response")))
                    .block(java.time.Duration.ofSeconds(5));
            return ResponseEntity.ok(ApiResponse.ok(response));
        } catch (Exception e) {
            String message = body.getOrDefault("message", "");
            String fallbackResponse = "[FALLBACK_BRIDGE] Empathetic Agent offline. Echo: '" +
                    (message.length() > 30 ? message.substring(0, 30) + "..." : message) + "'";
            return ResponseEntity.ok(ApiResponse.ok(Map.of("response", fallbackResponse)));
        }
    }
}
