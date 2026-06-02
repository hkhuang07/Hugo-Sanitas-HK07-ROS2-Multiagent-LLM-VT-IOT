"""
BlackboardService — Shared Memory Architecture for Cognitive Orchestration

Kiến trúc "Bảng đen chia sẻ" (Blackboard) cho phép các Agent độc lập ghi/đọc
trạng thái chung của bệnh nhân. Giúp Empathetic Agent có thể "biên dịch" 
kết luận y tế khô khan thành câu nói thấu cảm.

Triển khai: Redis (nếu sẵn) hoặc Singleton Pattern (nếu Redis chưa ready)
TTL: Mỗi entry có TTL 300s (5 phút) để tránh stale data
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import os

log = logging.getLogger("hk07.blackboard")

# ─── Blackboard Entry Schema ──────────────────────────────────────────────────
@dataclass
class ClinicalEntry:
    """Medical Agent writes clinical findings here"""
    agent_type: str = "MEDICAL"
    timestamp: str = ""
    alert_level: str = "NORMAL"  # NORMAL, WARNING, CRITICAL, STROKE
    vitals: Dict[str, Any] = None
    diagnosis: str = ""  # e.g. "Hemoptysis, elevated HR"
    action_recommended: str = ""  # e.g. "Call ambulance immediately"
    confidence_score: float = 0.8
    ttl_seconds: int = 300

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        if self.vitals is None:
            self.vitals = {}

    def is_expired(self) -> bool:
        """Check if this entry has expired"""
        entry_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        expiry_time = entry_time + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow().timestamp() > expiry_time.timestamp()


@dataclass
class EmotionalEntry:
    """Empathetic Agent infers emotional state"""
    agent_type: str = "EMPATHETIC"
    timestamp: str = ""
    detected_emotion: str = ""  # happy, anxious, sad, fearful, neutral
    emotional_intensity: float = 0.5  # 0.0 ~ 1.0
    tone_analysis: str = ""  # "voice trembling", "monotone", etc
    ttl_seconds: int = 300

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class ContextEntry:
    """Shared context for orchestration decisions"""
    agent_type: str = "ORCHESTRATOR"
    timestamp: str = ""
    user_query: str = ""
    current_agent: str = "ROUTER"
    required_tools: list = None  # ["analyze_clinical", "speak_empathetic"]
    ttl_seconds: int = 60

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        if self.required_tools is None:
            self.required_tools = []


# ─── Blackboard Service (In-Memory Singleton) ─────────────────────────────────
class BlackboardService:
    """
    Shared memory for HK-07 agents. 
    
    Design:
    - Uses Redis if available (via URL env var)
    - Falls back to in-memory dict if Redis unavailable
    - Each entry has TTL to prevent stale data
    - Thread-safe via asyncio locks
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BlackboardService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._use_redis = False
        self._redis_client = None
        self._in_memory_store: Dict[str, Dict[str, Any]] = {}
        
        # Detect if Redis is available and reachable. Prefer safe synchronous ping test
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            # Use sync client to verify server is reachable during init
            import redis as sync_redis
            sync_client = sync_redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1
            )
            sync_client.ping()
            # If ping succeeds, initialize async client
            import redis.asyncio as aioredis
            self._redis_client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1
            )
            self._use_redis = True
            log.info("[BLACKBOARD] Initialized with Redis backend: %s", redis_url)
        except Exception as e:
            # Any failure -> fall back to in-memory store without crashing
            log.info("[BLACKBOARD] Redis not available or unreachable (%s). Using in-memory fallback.", str(e)[:120])
            self._use_redis = False

    async def write_clinical(self, entry: ClinicalEntry) -> None:
        """Medical Agent writes clinical findings"""
        async with self._lock:
            key = f"blackboard:clinical:{entry.timestamp}"
            data = asdict(entry)
            
            if self._use_redis and self._redis_client:
                try:
                    await self._redis_client.setex(
                        key,
                        entry.ttl_seconds,
                        json.dumps(data)
                    )
                    log.debug("[BLACKBOARD] Clinical entry written to Redis: %s", key)
                except Exception as e:
                    log.error("[BLACKBOARD_REDIS_ERROR] Failed to write: %s", e)
                    # Fallback to in-memory
                    self._in_memory_store[key] = data
            else:
                self._in_memory_store[key] = data
                log.debug("[BLACKBOARD] Clinical entry written to memory: %s", key)

    async def read_latest_clinical(self) -> Optional[ClinicalEntry]:
        """Empathetic/Orchestrator reads latest clinical findings"""
        async with self._lock:
            if self._use_redis and self._redis_client:
                try:
                    # Scan for latest clinical entry
                    pattern = "blackboard:clinical:*"
                    keys = await self._redis_client.keys(pattern)
                    if not keys:
                        return None
                    
                    # Get latest (by key timestamp)
                    latest_key = sorted(keys)[-1]
                    data_str = await self._redis_client.get(latest_key)
                    if data_str:
                        data = json.loads(data_str)
                        return ClinicalEntry(**data)
                except Exception as e:
                    log.error("[BLACKBOARD_REDIS_ERROR] Failed to read clinical: %s", e)
                    # Fallback
            
            # In-memory fallback
            clinical_entries = [
                (k, v) for k, v in self._in_memory_store.items()
                if k.startswith("blackboard:clinical:")
            ]
            if not clinical_entries:
                return None
            
            latest_key, latest_data = sorted(clinical_entries)[-1]
            entry = ClinicalEntry(**latest_data)
            if entry.is_expired():
                del self._in_memory_store[latest_key]
                return None
            return entry

    async def write_emotional(self, entry: EmotionalEntry) -> None:
        """Empathetic Agent writes emotional analysis"""
        async with self._lock:
            key = f"blackboard:emotional:{entry.timestamp}"
            data = asdict(entry)
            
            if self._use_redis and self._redis_client:
                try:
                    await self._redis_client.setex(
                        key,
                        entry.ttl_seconds,
                        json.dumps(data)
                    )
                    log.debug("[BLACKBOARD] Emotional entry written to Redis: %s", key)
                except Exception as e:
                    log.error("[BLACKBOARD_REDIS_ERROR] Failed to write emotional: %s", e)
                    self._in_memory_store[key] = data
            else:
                self._in_memory_store[key] = data
                log.debug("[BLACKBOARD] Emotional entry written to memory: %s", key)

    async def read_latest_emotional(self) -> Optional[EmotionalEntry]:
        """Orchestrator reads latest emotional state"""
        async with self._lock:
            if self._use_redis and self._redis_client:
                try:
                    pattern = "blackboard:emotional:*"
                    keys = await self._redis_client.keys(pattern)
                    if not keys:
                        return None
                    
                    latest_key = sorted(keys)[-1]
                    data_str = await self._redis_client.get(latest_key)
                    if data_str:
                        data = json.loads(data_str)
                        return EmotionalEntry(**data)
                except Exception as e:
                    log.error("[BLACKBOARD_REDIS_ERROR] Failed to read emotional: %s", e)
            
            emotional_entries = [
                (k, v) for k, v in self._in_memory_store.items()
                if k.startswith("blackboard:emotional:")
            ]
            if not emotional_entries:
                return None
            
            latest_key, latest_data = sorted(emotional_entries)[-1]
            entry = EmotionalEntry(**latest_data)
            if entry.is_expired():
                del self._in_memory_store[latest_key]
                return None
            return entry

    async def write_context(self, entry: ContextEntry) -> None:
        """Orchestrator writes orchestration decisions"""
        async with self._lock:
            key = f"blackboard:context:{entry.timestamp}"
            data = asdict(entry)
            
            if self._use_redis and self._redis_client:
                try:
                    await self._redis_client.setex(
                        key,
                        entry.ttl_seconds,
                        json.dumps(data)
                    )
                    log.debug("[BLACKBOARD] Context entry written to Redis: %s", key)
                except Exception as e:
                    log.error("[BLACKBOARD_REDIS_ERROR] Failed to write context: %s", e)
                    self._in_memory_store[key] = data
            else:
                self._in_memory_store[key] = data

    async def read_latest_context(self) -> Optional[ContextEntry]:
        """Agents read orchestration context"""
        async with self._lock:
            if self._use_redis and self._redis_client:
                try:
                    pattern = "blackboard:context:*"
                    keys = await self._redis_client.keys(pattern)
                    if not keys:
                        return None
                    
                    latest_key = sorted(keys)[-1]
                    data_str = await self._redis_client.get(latest_key)
                    if data_str:
                        data = json.loads(data_str)
                        return ContextEntry(**data)
                except Exception as e:
                    log.error("[BLACKBOARD_REDIS_ERROR] Failed to read context: %s", e)
            
            context_entries = [
                (k, v) for k, v in self._in_memory_store.items()
                if k.startswith("blackboard:context:")
            ]
            if not context_entries:
                return None
            
            latest_key, latest_data = sorted(context_entries)[-1]
            entry = ContextEntry(**latest_data)
            if entry.is_expired():
                del self._in_memory_store[latest_key]
                return None
            return entry

    async def clear_expired(self) -> None:
        """Periodic cleanup of expired entries (call every 5 minutes)"""
        async with self._lock:
            if self._use_redis:
                # Redis handles TTL automatically
                pass
            else:
                # Manual cleanup for in-memory store
                expired_keys = [
                    k for k, v in self._in_memory_store.items()
                    if "timestamp" in v
                ]
                for key in expired_keys:
                    try:
                        data = self._in_memory_store[key]
                        entry_type = key.split(":")[1]
                        
                        if entry_type == "clinical":
                            entry = ClinicalEntry(**data)
                        elif entry_type == "emotional":
                            entry = EmotionalEntry(**data)
                        elif entry_type == "context":
                            entry = ContextEntry(**data)
                        else:
                            continue
                        
                        if entry.is_expired():
                            del self._in_memory_store[key]
                    except Exception:
                        pass
                
                log.debug("[BLACKBOARD] Cleanup complete. Entries: %d", len(self._in_memory_store))

    async def get_stats(self) -> Dict[str, int]:
        """Get stats for monitoring"""
        async with self._lock:
            if self._use_redis and self._redis_client:
                try:
                    clinical_count = len(await self._redis_client.keys("blackboard:clinical:*"))
                    emotional_count = len(await self._redis_client.keys("blackboard:emotional:*"))
                    context_count = len(await self._redis_client.keys("blackboard:context:*"))
                    return {
                        "clinical": clinical_count,
                        "emotional": emotional_count,
                        "context": context_count
                    }
                except Exception:
                    pass
            
            # In-memory stats
            return {
                "clinical": len([k for k in self._in_memory_store if k.startswith("blackboard:clinical:")]),
                "emotional": len([k for k in self._in_memory_store if k.startswith("blackboard:emotional:")]),
                "context": len([k for k in self._in_memory_store if k.startswith("blackboard:context:")]),
            }


# Singleton accessor
def get_blackboard() -> BlackboardService:
    """Get or create Blackboard singleton"""
    return BlackboardService()
