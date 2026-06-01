package com.hk07.domain.user.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data @Builder @NoArgsConstructor @AllArgsConstructor
public class MedicalProfileDto {
    private UUID id;
    private UUID userId;
    private String fullName;
    private Integer age;
    private String gender;
    private Float height;
    private Float weight;
    private String bloodType;
    private String medicalHistory;
    private String allergies;
    private String emergencyContactName;
    private String emergencyContactPhone;
}
