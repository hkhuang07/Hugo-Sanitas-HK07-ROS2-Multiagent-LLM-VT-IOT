package com.hk07.infrastructure.ai;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

/**
 * Groq API Client — Cloud AI Gateway
 *
 * Groq provides inference at 500-800 tokens/second on Llama 3 models.
 * Free tier sufficient for R&D (rate limits apply).
 *
 * Usage strategy:
 * - Empathetic Agent: llama3-8b-8192 (fast, light)
 * - Medical Agent: llama3-70b-8192 (more accurate for clinical reasoning)
 * - Safety Agent does NOT use LLM — it uses deterministic LiDAR thresholds
 *
 * Hardware constraint: All calls are async (WebClient reactive) — never block Virtual Threads.
 */
@Component
@Slf4j
public class GroqApiClient {

    private static final String GROQ_BASE_URL = "https://api.groq.com/openai/v1";
    private static final String EMPATHETIC_MODEL = "llama3-8b-8192";
    private static final String MEDICAL_MODEL = "llama-3.1-70b-versatile";

    @Value("${hk07.ai.groq.api-key:}")
    private String apiKey;

    private final WebClient webClient;

    public GroqApiClient() {
        this.webClient = WebClient.builder()
                .baseUrl(GROQ_BASE_URL)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }

    /**
     * Call Groq Chat Completion API asynchronously.
     *
     * @param systemPrompt  Instructions for the AI agent role
     * @param userMessage   The user context or sensor data summary
     * @param model         Model to use (empathetic vs medical)
     * @return Mono<String> with AI response text
     */
    public Mono<String> chat(String systemPrompt, String userMessage, String model) {
        if (apiKey.isBlank()) {
            log.warn("[GROQ_CLIENT] API key not configured — returning mock response");
            return Mono.just("[MOCK_GROQ_RESPONSE] Configure hk07.ai.groq.api-key in application.yml");
        }

        Map<String, Object> requestBody = Map.of(
            "model", model,
            "messages", List.of(
                Map.of("role", "system", "content", systemPrompt),
                Map.of("role", "user", "content", userMessage)
            ),
            "max_tokens", 512,        // Limit response size for RAM efficiency
            "temperature", 0.3        // Low temperature for clinical/safety contexts
        );

        return webClient.post()
                .uri("/chat/completions")
                .header("Authorization", "Bearer " + apiKey)
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(Map.class)
                .map(response -> {
                    try {
                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> choices = (List<Map<String, Object>>) response.get("choices");
                        Map<String, Object> firstChoice = choices.get(0);
                        @SuppressWarnings("unchecked")
                        Map<String, String> messageMap = (Map<String, String>) firstChoice.get("message");
                        String content = messageMap.get("content");
                        log.debug("[GROQ_RESPONSE] Model: {} | Tokens: ~{}", model, content.length() / 4);
                        return content;
                    } catch (Exception e) {
                        log.error("[GROQ_PARSE_ERROR] {}", e.getMessage());
                        return "[ERROR] Failed to parse Groq response";
                    }
                })
                .onErrorReturn("[GROQ_NETWORK_ERROR] Cannot reach api.groq.com");
    }

    /** Shorthand for Empathetic Agent calls */
    public Mono<String> chatEmpathetic(String systemPrompt, String context) {
        return chat(systemPrompt, context, EMPATHETIC_MODEL);
    }

    /** Shorthand for Medical Agent calls */
    public Mono<String> chatMedical(String systemPrompt, String vitalSummary) {
        return chat(systemPrompt, vitalSummary, MEDICAL_MODEL);
    }
}
