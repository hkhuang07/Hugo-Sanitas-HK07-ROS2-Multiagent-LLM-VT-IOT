package com.hk07.domain.user.repository;

import com.hk07.domain.user.entity.MedicalProfileEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface MedicalProfileRepository extends JpaRepository<MedicalProfileEntity, UUID> {
    Optional<MedicalProfileEntity> findByUserId(UUID userId);
}
