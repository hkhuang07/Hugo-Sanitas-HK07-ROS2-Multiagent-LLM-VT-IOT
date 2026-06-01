package com.hk07.domain.user.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "recovery_codes", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"user_id", "code"})
})
@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor
public class RecoveryCodeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private UserEntity user;

    @Column(nullable = false, length = 8)
    private String code;

    @Column(nullable = false)
    @Builder.Default
    private boolean used = false;

    @CreationTimestamp
    private LocalDateTime createdAt;
}
