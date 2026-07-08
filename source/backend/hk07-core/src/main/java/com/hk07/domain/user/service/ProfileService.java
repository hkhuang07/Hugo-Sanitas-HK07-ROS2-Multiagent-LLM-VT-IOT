package com.hk07.domain.user.service;

import com.hk07.common.exception.HK07NotFoundException;
import com.hk07.domain.user.dto.MedicalProfileDto;
import com.hk07.domain.user.entity.MedicalProfileEntity;
import com.hk07.domain.user.entity.UserEntity;
import com.hk07.domain.user.repository.MedicalProfileRepository;
import com.hk07.domain.user.repository.UserRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Service
@Slf4j
public class ProfileService {

    private final UserRepository userRepository;
    private final MedicalProfileRepository medicalProfileRepository;
    private final WebClient webClient;

    public ProfileService(
            UserRepository userRepository,
            MedicalProfileRepository medicalProfileRepository,
            @Value("${AGENT_ENGINE_URL:http://127.0.0.1:8889}") String agentEngineUrl) {
        this.userRepository = userRepository;
        this.medicalProfileRepository = medicalProfileRepository;
        this.webClient = WebClient.builder()
                .baseUrl(agentEngineUrl)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }

    @Transactional(readOnly = true)
    public MedicalProfileDto getProfileByUserId(UUID userId) {
        MedicalProfileEntity profile = medicalProfileRepository.findByUserId(userId)
                .orElseThrow(() -> new HK07NotFoundException("MedicalProfile", userId.toString()));
        return toDto(profile);
    }

    @Transactional
    public MedicalProfileDto updateProfile(UUID userId, MedicalProfileDto dto) {
        UserEntity user = userRepository.findById(userId)
                .orElseThrow(() -> new HK07NotFoundException("User", userId.toString()));

        MedicalProfileEntity profile = medicalProfileRepository.findByUserId(userId)
                .orElseGet(() -> MedicalProfileEntity.builder().user(user).build());

        profile.setFullName(dto.getFullName());
        profile.setAge(dto.getAge());
        profile.setGender(dto.getGender());
        profile.setHeight(dto.getHeight());
        profile.setWeight(dto.getWeight());
        profile.setBloodType(dto.getBloodType());
        profile.setMedicalHistory(dto.getMedicalHistory());
        profile.setAllergies(dto.getAllergies());
        profile.setEmergencyContactName(dto.getEmergencyContactName());
        profile.setEmergencyContactPhone(dto.getEmergencyContactPhone());

        MedicalProfileEntity saved = medicalProfileRepository.save(profile);
        log.info("[PROFILE_UPDATE] Successfully updated medical profile for user: {}", userId);

        // Sync with Python AI Agent memory asynchronously
        syncWithAiAgent(userId, saved).subscribe(
            success -> log.info("[AI_SYNC] Sync success for user: {}", userId),
            error -> log.error("[AI_SYNC_ERROR] Failed to sync for user {}: {}", userId, error.getMessage())
        );

        return toDto(saved);
    }

    public Mono<Void> syncWithAiAgent(UUID userId, MedicalProfileEntity profile) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("userId", userId.toString());
        payload.put("fullName", profile.getFullName());
        payload.put("age", profile.getAge());
        payload.put("gender", profile.getGender());
        payload.put("height", profile.getHeight());
        payload.put("weight", profile.getWeight());
        payload.put("bloodType", profile.getBloodType());
        payload.put("medicalHistory", profile.getMedicalHistory());
        payload.put("allergies", profile.getAllergies());
        payload.put("emergencyContactName", profile.getEmergencyContactName());
        payload.put("emergencyContactPhone", profile.getEmergencyContactPhone());

        return webClient.post()
                .uri("/api/v1/memory/sync_profile")
                .bodyValue(payload)
                .retrieve()
                .bodyToMono(Void.class)
                .onErrorResume(e -> {
                    log.warn("[AI_SYNC_WARNING] Error communicating with AI Agent: {}", e.getMessage());
                    return Mono.empty();
                });
    }

    private MedicalProfileDto toDto(MedicalProfileEntity p) {
        return MedicalProfileDto.builder()
                .id(p.getId())
                .userId(p.getUser().getId())
                .fullName(p.getFullName())
                .age(p.getAge())
                .gender(p.getGender())
                .height(p.getHeight())
                .weight(p.getWeight())
                .bloodType(p.getBloodType())
                .medicalHistory(p.getMedicalHistory())
                .allergies(p.getAllergies())
                .emergencyContactName(p.getEmergencyContactName())
                .emergencyContactPhone(p.getEmergencyContactPhone())
                .build();
    }
}
