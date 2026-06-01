package com.hk07.domain.audit.repository;

import com.hk07.domain.audit.entity.AuditLogEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface AuditLogRepository extends JpaRepository<AuditLogEntity, UUID> {

    List<AuditLogEntity> findTop50ByActorIdOrderByExecutedAtDesc(UUID actorId);

    List<AuditLogEntity> findTop100ByActionTypeOrderByExecutedAtDesc(String actionType);

    List<AuditLogEntity> findByExecutedAtAfterOrderByExecutedAtDesc(Instant since);
}
