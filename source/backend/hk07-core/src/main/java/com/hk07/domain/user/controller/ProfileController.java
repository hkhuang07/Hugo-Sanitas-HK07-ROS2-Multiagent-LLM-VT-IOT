package com.hk07.domain.user.controller;

import com.hk07.common.dto.ApiResponse;
import com.hk07.domain.user.dto.MedicalProfileDto;
import com.hk07.domain.user.service.ProfileService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/profile")
@RequiredArgsConstructor
public class ProfileController {

    private final ProfileService profileService;

    @GetMapping("/me")
    public ResponseEntity<ApiResponse<MedicalProfileDto>> getMyProfile(Authentication auth) {
        UUID userId = UUID.fromString(auth.getName());
        return ResponseEntity.ok(ApiResponse.ok(profileService.getProfileByUserId(userId)));
    }

    @PostMapping("/update")
    public ResponseEntity<ApiResponse<MedicalProfileDto>> updateProfile(
            Authentication auth,
            @Valid @RequestBody MedicalProfileDto dto) {
        UUID userId = UUID.fromString(auth.getName());
        MedicalProfileDto updated = profileService.updateProfile(userId, dto);
        return ResponseEntity.ok(ApiResponse.ok("Medical profile updated successfully", updated));
    }
}
