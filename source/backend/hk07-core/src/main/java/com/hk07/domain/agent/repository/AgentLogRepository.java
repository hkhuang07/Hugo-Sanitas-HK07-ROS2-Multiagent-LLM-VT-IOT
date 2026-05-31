package com.hk07.domain.agent.repository;

import com.hk07.common.enums.AgentType;
import com.hk07.domain.agent.entity.AgentLogEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.UUID;

public interface AgentLogRepository extends JpaRepository<AgentLogEntity, UUID> {

    Page<AgentLogEntity> findByAgentTypeOrderByTriggeredAtDesc(AgentType agentType, Pageable pageable);

    Page<AgentLogEntity> findAllByOrderByTriggeredAtDesc(Pageable pageable);

    /** Count decisions per agent type for dashboard stats panel */
    @Query("SELECT a.agentType, COUNT(a) FROM AgentLogEntity a GROUP BY a.agentType")
    java.util.List<Object[]> countByAgentType();
}
