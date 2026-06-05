package com.hk07.domain.auth.service;

import com.hk07.common.enums.UserRole;
import com.hk07.common.exception.HK07BusinessException;
import com.hk07.common.exception.HK07NotFoundException;
import com.hk07.domain.auth.dto.AuthDto;
import com.hk07.domain.user.entity.MedicalProfileEntity;
import com.hk07.domain.user.entity.RecoveryCodeEntity;
import com.hk07.domain.user.entity.UserEntity;
import com.hk07.domain.user.repository.MedicalProfileRepository;
import com.hk07.domain.user.repository.RecoveryCodeRepository;
import com.hk07.domain.user.repository.UserRepository;
import com.hk07.domain.user.service.ProfileService;
import com.hk07.infrastructure.security.JwtService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Auth Service — Phase 02
 *
 * Handles login, registration, token refresh, and logout.
 * Refresh tokens are stored in Redis with TTL for revocability.
 *
 * Redis key pattern: "hk07:refresh:{userId}:{tokenHash}"
 * This allows revoking ALL sessions for a user by prefix-scanning.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final StringRedisTemplate redis;
    
    private final MedicalProfileRepository medicalProfileRepository;
    private final RecoveryCodeRepository recoveryCodeRepository;
    private final ProfileService profileService;

    @Value("${hk07.security.jwt.refresh-token-expiry-ms}")
    private long refreshExpiryMs;

    /** Authenticate with email + password, return token pair */
    @Transactional
    public AuthDto.TokenResponse login(AuthDto.LoginRequest req) {
        UserEntity user = userRepository.findByEmail(req.getEmail())
                .orElseThrow(() -> new BadCredentialsException("Invalid credentials"));

        if (!passwordEncoder.matches(req.getPassword(), user.getPasswordHash())) {
            log.warn("[AUTH_LOGIN_FAIL] email={}", req.getEmail());
            throw new BadCredentialsException("Invalid credentials");
        }

        // Update last seen timestamp (non-blocking via Virtual Thread)
        userRepository.updateLastSeen(user.getId(), LocalDateTime.now());

        return buildTokenResponse(user);
    }

    /** Authenticate with device PIN (recovery code) */
    @Transactional
    public AuthDto.TokenResponse pinLogin(AuthDto.PinLoginRequest req) {
        RecoveryCodeEntity codeEntity = recoveryCodeRepository
                .findFirstByCodeAndUsed(req.getPin(), false)
                .orElseThrow(() -> new BadCredentialsException("Invalid or expired PIN code"));

        codeEntity.setUsed(true);
        recoveryCodeRepository.save(codeEntity);

        UserEntity user = codeEntity.getUser();

        // Update last seen timestamp
        userRepository.updateLastSeen(user.getId(), LocalDateTime.now());

        log.info("[AUTH_PIN_LOGIN] Successful PIN login for user: {}", user.getEmail());

        return buildTokenResponse(user);
    }


    /** Register a new user (OWNER role by default) */
    @Transactional
    public AuthDto.TokenResponse register(AuthDto.RegisterRequest req) {
        if (userRepository.existsByEmail(req.getEmail())) {
            throw new HK07BusinessException("Email already registered: " + req.getEmail());
        }

        UserEntity user = UserEntity.builder()
                .displayName(req.getDisplayName())
                .email(req.getEmail())
                .passwordHash(passwordEncoder.encode(req.getPassword()))
                .role(UserRole.OWNER)
                .build();

        userRepository.save(user);
        log.info("[AUTH_REGISTER] New user: {} ({})", req.getDisplayName(), req.getEmail());

        // Create Medical Profile
        MedicalProfileEntity profile = MedicalProfileEntity.builder()
                .user(user)
                .fullName(req.getFullName())
                .age(req.getAge())
                .gender(req.getGender())
                .height(req.getHeight())
                .weight(req.getWeight())
                .bloodType(req.getBloodType())
                .medicalHistory(req.getMedicalHistory())
                .allergies(req.getAllergies())
                .emergencyContactName(req.getEmergencyContactName())
                .emergencyContactPhone(req.getEmergencyContactPhone())
                .build();
        medicalProfileRepository.save(profile);

        // Generate 5 Recovery Codes
        List<String> recoveryCodes = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            String code = generateRandomAlphanumeric(8);
            recoveryCodes.add(code);
            recoveryCodeRepository.save(RecoveryCodeEntity.builder()
                    .user(user)
                    .code(code)
                    .used(false)
                    .build());
        }

        // Sync with AI Agent memory
        profileService.syncWithAiAgent(user.getId(), profile).subscribe(
            success -> log.info("[AI_SYNC] Registration sync success for user: {}", user.getId()),
            error -> log.error("[AI_SYNC_ERROR] Registration sync failed for user {}: {}", user.getId(), error.getMessage())
        );

        AuthDto.TokenResponse res = buildTokenResponse(user);
        res.setRecoveryCodes(recoveryCodes);
        return res;
    }

    /** Rotate refresh token — invalidate old, issue new pair */
    @Transactional
    public AuthDto.TokenResponse refresh(AuthDto.RefreshRequest req) {
        String token = req.getRefreshToken();

        if (!jwtService.isTokenValid(token)) {
            throw new HK07BusinessException("Invalid or expired refresh token");
        }

        String userId = jwtService.extractUserId(token);
        String redisKey = "hk07:refresh:" + userId + ":" + token.hashCode();

        if (Boolean.FALSE.equals(redis.hasKey(redisKey))) {
            log.warn("[AUTH_REFRESH_REVOKED] Attempted to use revoked refresh token, userId={}", userId);
            throw new HK07BusinessException("Refresh token has been revoked");
        }

        // Invalidate used token (rotation — prevents replay attacks)
        redis.delete(redisKey);

        UserEntity user = userRepository.findById(UUID.fromString(userId))
                .orElseThrow(() -> new HK07NotFoundException("User", userId));

        return buildTokenResponse(user);
    }

    /** Revoke refresh token on logout */
    public void logout(String refreshToken) {
        if (jwtService.isTokenValid(refreshToken)) {
            String userId = jwtService.extractUserId(refreshToken);
            String redisKey = "hk07:refresh:" + userId + ":" + refreshToken.hashCode();
            redis.delete(redisKey);
            log.info("[AUTH_LOGOUT] userId={}", userId);
        }
    }

    @Transactional
    public void changePassword(UUID userId, AuthDto.ChangePasswordRequest req) {
        UserEntity user = userRepository.findById(userId)
                .orElseThrow(() -> new HK07NotFoundException("User", userId.toString()));

        if (!passwordEncoder.matches(req.getOldPassword(), user.getPasswordHash())) {
            throw new BadCredentialsException("Invalid old password");
        }

        user.setPasswordHash(passwordEncoder.encode(req.getNewPassword()));
        userRepository.save(user);
        log.info("[AUTH_CHANGE_PASSWORD] Password updated for userId: {}", userId);
    }

    @Transactional
    public void resetPassword(AuthDto.ResetPasswordRequest req) {
        UserEntity user = userRepository.findByEmail(req.getEmail())
                .orElseThrow(() -> new HK07NotFoundException("User with email", req.getEmail()));

        RecoveryCodeEntity codeEntity = recoveryCodeRepository
                .findByUserIdAndCodeAndUsed(user.getId(), req.getRecoveryCode(), false)
                .orElseThrow(() -> new HK07BusinessException("Invalid or already used recovery code"));

        codeEntity.setUsed(true);
        recoveryCodeRepository.save(codeEntity);

        user.setPasswordHash(passwordEncoder.encode(req.getNewPassword()));
        userRepository.save(user);
        log.info("[AUTH_RESET_PASSWORD] Password reset successfully for email: {}", req.getEmail());
    }

    // ─── Private Helpers ─────────────────────────────────────────────────────
    private AuthDto.TokenResponse buildTokenResponse(UserEntity user) {
        String userId = user.getId().toString();
        String accessToken = jwtService.generateAccessToken(userId, user.getEmail(), user.getRole().name());
        String refreshToken = jwtService.generateRefreshToken(userId);

        // Store refresh token in Redis with TTL
        String redisKey = "hk07:refresh:" + userId + ":" + refreshToken.hashCode();
        redis.opsForValue().set(redisKey, "valid", Duration.ofMillis(refreshExpiryMs));

        long expiresAt = System.currentTimeMillis() + 900_000L; // 15 min
        return AuthDto.TokenResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .accessTokenExpiresAt(expiresAt)
                .userId(userId)
                .role(user.getRole().name())
                .email(user.getEmail())  // Returned so frontend restores full profile on refresh
                .build();
    }

    private String generateRandomAlphanumeric(int length) {
        String chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        java.security.SecureRandom random = new java.security.SecureRandom();
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            sb.append(chars.charAt(random.nextInt(chars.length())));
        }
        return sb.toString();
    }
}
