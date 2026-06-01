package com.hk07.domain.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;
import java.util.List;

public class AuthDto {

    @Data
    public static class LoginRequest {
        @NotBlank @Email
        private String email;
        @NotBlank @Size(min = 8, max = 128)
        private String password;
    }

    @Data
    public static class RegisterRequest {
        @NotBlank @Size(min = 2, max = 100)
        private String displayName;
        
        @NotBlank @Email
        private String email;
        
        @NotBlank @Size(min = 8, max = 128)
        private String password;
        
        // Medical Baseline fields
        private String fullName;
        private Integer age;
        private String gender;
        private Float height;
        private Float weight;
        private String bloodType;
        private String medicalHistory;
        private String allergies;
        
        // Emergency contact fields
        private String emergencyContactName;
        private String emergencyContactPhone;
    }

    @Data
    public static class RefreshRequest {
        @NotBlank
        private String refreshToken;
    }

    @lombok.Builder
    @Data
    public static class TokenResponse {
        private String accessToken;
        private String refreshToken;
        private long accessTokenExpiresAt;  // Unix epoch ms
        private String userId;
        private String role;
        private List<String> recoveryCodes; // Set only during registration
    }

    @Data
    public static class ChangePasswordRequest {
        @NotBlank
        private String oldPassword;
        
        @NotBlank @Size(min = 8, max = 128)
        private String newPassword;
    }

    @Data
    public static class ResetPasswordRequest {
        @NotBlank @Email
        private String email;
        
        @NotBlank @Size(min = 8, max = 8)
        private String recoveryCode;
        
        @NotBlank @Size(min = 8, max = 128)
        private String newPassword;
    }
}
