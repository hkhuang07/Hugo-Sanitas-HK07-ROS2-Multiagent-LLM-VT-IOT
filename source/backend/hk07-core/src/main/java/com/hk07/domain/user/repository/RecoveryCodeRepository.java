package com.hk07.domain.user.repository;

import com.hk07.domain.user.entity.RecoveryCodeEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface RecoveryCodeRepository extends JpaRepository<RecoveryCodeEntity, UUID> {
    List<RecoveryCodeEntity> findByUserId(UUID userId);
    Optional<RecoveryCodeEntity> findByUserIdAndCodeAndUsed(UUID userId, String code, boolean used);
    Optional<RecoveryCodeEntity> findFirstByCodeAndUsed(String code, boolean used);
}

