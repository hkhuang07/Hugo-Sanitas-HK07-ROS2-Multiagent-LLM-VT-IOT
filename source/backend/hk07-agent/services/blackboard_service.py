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
import contextvars
import fnmatch

log = logging.getLogger("hk07.blackboard")

# ContextVar for request-local user context isolation
current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_user_id", default="a0000000-0000-0000-0000-000000000001")
current_auth_token: contextvars.ContextVar[str] = contextvars.ContextVar("current_auth_token", default="")


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

    def is_expired(self) -> bool:
        """Check if this entry has expired"""
        entry_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        expiry_time = entry_time + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow().timestamp() > expiry_time.timestamp()


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

    def is_expired(self) -> bool:
        """Check if this entry has expired"""
        entry_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        expiry_time = entry_time + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow().timestamp() > expiry_time.timestamp()


@dataclass
class ActionPlanEntry:
    """Structured action plan containing steps for robot actuators"""
    agent_type: str = "ACTION"
    timestamp: str = ""
    plan_id: str = ""
    steps: list = None  # list of dicts: [{ type, mqtt_topic, payload, requires_confirm }]
    status: str = "PENDING"  # PENDING, AWAITING_CONFIRM, EXECUTING, COMPLETED, FAILED, CANCELLED
    current_step_index: int = 0
    ttl_seconds: int = 300

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        if self.steps is None:
            self.steps = []

    def is_expired(self) -> bool:
        entry_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        expiry_time = entry_time + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow().timestamp() > expiry_time.timestamp()


# ─── Blackboard Service (In-Memory Singleton) ─────────────────────────────────
class BlackboardService:
    """
    Shared memory for HK-07 agents. 
    
    Design:
    - Uses Redis if available (via URL env var)
    - Falls back to in-memory dict if Redis unavailable
    - Each entry has TTL to prevent stale data
    - Thread-safe via asyncio locks
    - Built-in Circuit Breaker to bypass Redis and prevent endpoint latency on timeout
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
        
        # Circuit Breaker state
        self._redis_healthy = True
        self._last_redis_fail_ts = 0.0
        self._redis_fail_cooldown = 30.0 # bypass Redis for 30s on failure (devmode)
        
        import sys
        
        # Detect if Redis is available and reachable. Prefer safe synchronous ping test.
        # In Docker Compose, REDIS_HOST should be the service name (hk07-redis), not localhost.
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")
        redis_db = os.getenv("REDIS_DB", "0")
        redis_url = os.getenv("REDIS_URL") or f"redis://{redis_host}:{redis_port}/{redis_db}"
        
        # Determine default gateway (WSL IP) to handle WSL bridge configurations
        default_gateway = os.getenv("DEFAULT_GATEWAY") or os.getenv("WIFI_IP")
        if not default_gateway:
            if sys.platform.startswith("win"):
                try:
                    from utils.ip_scanner import get_default_route_info
                    gw_ip, _ = get_default_route_info()
                    if gw_ip:
                        default_gateway = gw_ip
                except Exception:
                    pass
            elif sys.platform.startswith("linux"):
                try:
                    with open("/proc/net/route", "r") as f:
                        for line in f:
                            fields = line.strip().split()
                            if len(fields) >= 3 and fields[1] == "00000000":
                                hex_ip = fields[2]
                                ip_bytes = [int(hex_ip[i:i+2], 16) for i in range(0, 8, 2)]
                                default_gateway = ".".join(map(str, reversed(ip_bytes)))
                                break
                except Exception:
                    pass

        redis_urls_to_try = []
        if default_gateway and default_gateway != "127.0.0.1" and ("127.0.0.1" in redis_url or "localhost" in redis_url):
            fallback_url = redis_url.replace("127.0.0.1", default_gateway).replace("localhost", default_gateway)
            redis_urls_to_try.append(fallback_url)
        redis_urls_to_try.append(redis_url)

        connected = False
        for url in redis_urls_to_try:
            try:
                import redis as sync_redis
                # Ping test with a reasonable timeout
                sync_client = sync_redis.Redis.from_url(
                    url,
                    decode_responses=True,
                    socket_connect_timeout=5.0,
                    socket_timeout=5.0
                )
                sync_client.ping()
                
                # If ping succeeds, initialize async client
                import redis.asyncio as aioredis
                self._redis_client = aioredis.from_url(
                    url,
                    decode_responses=True,
                    socket_connect_timeout=10.0,
                    socket_timeout=10.0,  # 10s timeout for devmode hardware
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                self._use_redis = True
                log.info("[BLACKBOARD] Initialized with Redis backend: %s", url)
                connected = True
                break
            except Exception as e:
                log.debug("[BLACKBOARD] Redis attempt failed for %s: %s", url, str(e)[:120])

        if not connected:
            log.warning("[BLACKBOARD] Redis not available or unreachable on any tried endpoint. Using in-memory fallback.")
            self._use_redis = False

    def _should_use_redis(self) -> bool:
        if not self._use_redis or not self._redis_client:
            return False
        if not self._redis_healthy:
            if time.time() - self._last_redis_fail_ts > self._redis_fail_cooldown:
                log.info("[BLACKBOARD] Redis cooldown expired. Retrying connection...")
                return True
            return False
        return True

    def _handle_redis_failure(self, error: Exception):
        log.error("[BLACKBOARD_REDIS_ERROR] Redis connection failed/timed out: %s. Tripping circuit breaker (bypassing Redis for %.1fs).", error, self._redis_fail_cooldown)
        self._redis_healthy = False
        self._last_redis_fail_ts = time.time()

    async def write_clinical(self, entry: ClinicalEntry, user_id: str = None) -> None:
        """Medical Agent writes clinical findings"""
        if user_id is None:
            user_id = current_user_id.get()
        key = f"blackboard:clinical:{user_id}:{entry.timestamp}"
        latest_key = f"blackboard:clinical:{user_id}:latest"
        data = asdict(entry)
        
        # Always write to local memory first
        self._in_memory_store[key] = data
        self._in_memory_store[latest_key] = data
        
        if self._should_use_redis():
            try:
                await self._redis_client.setex(key, entry.ttl_seconds, json.dumps(data))
                await self._redis_client.setex(latest_key, entry.ttl_seconds, json.dumps(data))
                log.debug("[BLACKBOARD] Clinical entry written to Redis: %s", key)
                self._redis_healthy = True
            except Exception as e:
                self._handle_redis_failure(e)

    async def read_latest_clinical(self, user_id: str = None) -> Optional[ClinicalEntry]:
        """Empathetic/Orchestrator reads latest clinical findings"""
        if user_id is None:
            user_id = current_user_id.get()
        latest_key = f"blackboard:clinical:{user_id}:latest"
        if self._should_use_redis():
            try:
                data_str = await self._redis_client.get(latest_key)
                self._redis_healthy = True
                if data_str:
                    data = json.loads(data_str)
                    self._in_memory_store[latest_key] = data
                    return ClinicalEntry(**data)
            except Exception as e:
                log.error("[BLACKBOARD_REDIS_ERROR] Failed to read clinical from latest key: %s. Trying fallback scan.", e)
                
            try:
                # Fallback scan for latest clinical entry
                pattern = f"blackboard:clinical:{user_id}:*"
                keys = await self._redis_client.keys(pattern)
                self._redis_healthy = True
                if keys:
                    sorted_keys = sorted([k for k in keys if not k.endswith(":latest")])
                    if sorted_keys:
                        latest_k = sorted_keys[-1]
                        data_str = await self._redis_client.get(latest_k)
                        if data_str:
                            data = json.loads(data_str)
                            self._in_memory_store[latest_key] = data
                            self._in_memory_store[latest_k] = data
                            return ClinicalEntry(**data)
            except Exception as e:
                self._handle_redis_failure(e)
        
        # In-memory lookup
        latest_data = self._in_memory_store.get(latest_key)
        if latest_data:
            entry = ClinicalEntry(**latest_data)
            if not entry.is_expired():
                return entry
            else:
                try:
                    del self._in_memory_store[latest_key]
                except KeyError:
                    pass
        
        # In-memory fallback scan
        clinical_entries = [
            (k, v) for k, v in self._in_memory_store.items()
            if k.startswith(f"blackboard:clinical:{user_id}:") and not k.endswith(":latest")
        ]
        if not clinical_entries:
            return None
        
        latest_k, latest_data = sorted(clinical_entries)[-1]
        entry = ClinicalEntry(**latest_data)
        if entry.is_expired():
            try:
                del self._in_memory_store[latest_k]
            except KeyError:
                pass
            return None
        return entry

    async def write_emotional(self, entry: EmotionalEntry, user_id: str = None) -> None:
        """Empathetic Agent writes emotional analysis"""
        if user_id is None:
            user_id = current_user_id.get()
        key = f"blackboard:emotional:{user_id}:{entry.timestamp}"
        latest_key = f"blackboard:emotional:{user_id}:latest"
        data = asdict(entry)
        
        # Always write to local memory first
        self._in_memory_store[key] = data
        self._in_memory_store[latest_key] = data
        
        if self._should_use_redis():
            try:
                await self._redis_client.setex(key, entry.ttl_seconds, json.dumps(data))
                await self._redis_client.setex(latest_key, entry.ttl_seconds, json.dumps(data))
                log.debug("[BLACKBOARD] Emotional entry written to Redis: %s", key)
                self._redis_healthy = True
            except Exception as e:
                self._handle_redis_failure(e)

    async def read_latest_emotional(self, user_id: str = None) -> Optional[EmotionalEntry]:
        """Orchestrator reads latest emotional state"""
        if user_id is None:
            user_id = current_user_id.get()
        latest_key = f"blackboard:emotional:{user_id}:latest"
        if self._should_use_redis():
            try:
                data_str = await self._redis_client.get(latest_key)
                self._redis_healthy = True
                if data_str:
                    data = json.loads(data_str)
                    self._in_memory_store[latest_key] = data
                    return EmotionalEntry(**data)
            except Exception as e:
                log.error("[BLACKBOARD_REDIS_ERROR] Failed to read emotional from latest key: %s. Trying fallback scan.", e)
                
            try:
                pattern = f"blackboard:emotional:{user_id}:*"
                keys = await self._redis_client.keys(pattern)
                self._redis_healthy = True
                if keys:
                    sorted_keys = sorted([k for k in keys if not k.endswith(":latest")])
                    if sorted_keys:
                        latest_k = sorted_keys[-1]
                        data_str = await self._redis_client.get(latest_k)
                        if data_str:
                            data = json.loads(data_str)
                            self._in_memory_store[latest_key] = data
                            self._in_memory_store[latest_k] = data
                            return EmotionalEntry(**data)
            except Exception as e:
                self._handle_redis_failure(e)
        
        # In-memory lookup
        latest_data = self._in_memory_store.get(latest_key)
        if latest_data:
            entry = EmotionalEntry(**latest_data)
            if not entry.is_expired():
                return entry
            else:
                try:
                    del self._in_memory_store[latest_key]
                except KeyError:
                    pass
        
        # In-memory fallback scan
        emotional_entries = [
            (k, v) for k, v in self._in_memory_store.items()
            if k.startswith(f"blackboard:emotional:{user_id}:") and not k.endswith(":latest")
        ]
        if not emotional_entries:
            return None
        
        latest_k, latest_data = sorted(emotional_entries)[-1]
        entry = EmotionalEntry(**latest_data)
        if entry.is_expired():
            try:
                del self._in_memory_store[latest_k]
            except KeyError:
                pass
            return None
        return entry

    async def write_context(self, entry: ContextEntry, user_id: str = None) -> None:
        """Orchestrator writes orchestration decisions"""
        if user_id is None:
            user_id = current_user_id.get()
        key = f"blackboard:context:{user_id}:{entry.timestamp}"
        latest_key = f"blackboard:context:{user_id}:latest"
        data = asdict(entry)
        
        # Always write to local memory first
        self._in_memory_store[key] = data
        self._in_memory_store[latest_key] = data
        
        if self._should_use_redis():
            try:
                await self._redis_client.setex(key, entry.ttl_seconds, json.dumps(data))
                await self._redis_client.setex(latest_key, entry.ttl_seconds, json.dumps(data))
                log.debug("[BLACKBOARD] Context entry written to Redis: %s", key)
                self._redis_healthy = True
            except Exception as e:
                self._handle_redis_failure(e)

    async def read_latest_context(self, user_id: str = None) -> Optional[ContextEntry]:
        """Agents read orchestration context"""
        if user_id is None:
            user_id = current_user_id.get()
        latest_key = f"blackboard:context:{user_id}:latest"
        if self._should_use_redis():
            try:
                data_str = await self._redis_client.get(latest_key)
                self._redis_healthy = True
                if data_str:
                    data = json.loads(data_str)
                    self._in_memory_store[latest_key] = data
                    return ContextEntry(**data)
            except Exception as e:
                log.error("[BLACKBOARD_REDIS_ERROR] Failed to read context from latest key: %s. Trying fallback scan.", e)
                
            try:
                pattern = f"blackboard:context:{user_id}:*"
                keys = await self._redis_client.keys(pattern)
                self._redis_healthy = True
                if keys:
                    sorted_keys = sorted([k for k in keys if not k.endswith(":latest")])
                    if sorted_keys:
                        latest_k = sorted_keys[-1]
                        data_str = await self._redis_client.get(latest_k)
                        if data_str:
                            data = json.loads(data_str)
                            self._in_memory_store[latest_key] = data
                            self._in_memory_store[latest_k] = data
                            return ContextEntry(**data)
            except Exception as e:
                self._handle_redis_failure(e)
        
        # In-memory lookup
        latest_data = self._in_memory_store.get(latest_key)
        if latest_data:
            entry = ContextEntry(**latest_data)
            if not entry.is_expired():
                return entry
            else:
                try:
                    del self._in_memory_store[latest_key]
                except KeyError:
                    pass
        
        # In-memory fallback scan
        context_entries = [
            (k, v) for k, v in self._in_memory_store.items()
            if k.startswith(f"blackboard:context:{user_id}:") and not k.endswith(":latest")
        ]
        if not context_entries:
            return None
        
        latest_k, latest_data = sorted(context_entries)[-1]
        entry = ContextEntry(**latest_data)
        if entry.is_expired():
            try:
                del self._in_memory_store[latest_k]
            except KeyError:
                pass
            return None
        return entry

    async def write_action_plan(self, entry: ActionPlanEntry, user_id: str = None) -> None:
        """Action Agent / Orchestrator writes action plans"""
        if user_id is None:
            user_id = current_user_id.get()
        key = f"blackboard:action_plan:{user_id}:{entry.plan_id or entry.timestamp}"
        latest_key = f"blackboard:action_plan:{user_id}:latest"
        data = asdict(entry)
        
        # Always write to local memory first
        self._in_memory_store[key] = data
        self._in_memory_store[latest_key] = data
        
        if self._should_use_redis():
            try:
                await self._redis_client.setex(key, entry.ttl_seconds, json.dumps(data))
                await self._redis_client.setex(latest_key, entry.ttl_seconds, json.dumps(data))
                log.debug("[BLACKBOARD] Action plan written to Redis: %s", key)
                self._redis_healthy = True
            except Exception as e:
                self._handle_redis_failure(e)

    async def read_latest_action_plan(self, user_id: str = None) -> Optional[ActionPlanEntry]:
        """Read latest action plan from Blackboard"""
        if user_id is None:
            user_id = current_user_id.get()
        latest_key = f"blackboard:action_plan:{user_id}:latest"
        if self._should_use_redis():
            try:
                data_str = await self._redis_client.get(latest_key)
                self._redis_healthy = True
                if data_str:
                    data = json.loads(data_str)
                    self._in_memory_store[latest_key] = data
                    return ActionPlanEntry(**data)
            except Exception as e:
                log.error("[BLACKBOARD_REDIS_ERROR] Failed to read action plan from latest key: %s. Trying fallback scan.", e)
                
            try:
                pattern = f"blackboard:action_plan:{user_id}:*"
                keys = await self._redis_client.keys(pattern)
                self._redis_healthy = True
                if keys:
                    sorted_keys = sorted([k for k in keys if not k.endswith(":latest")])
                    if sorted_keys:
                        latest_k = sorted_keys[-1]
                        data_str = await self._redis_client.get(latest_k)
                        if data_str:
                            data = json.loads(data_str)
                            self._in_memory_store[latest_key] = data
                            self._in_memory_store[latest_k] = data
                            return ActionPlanEntry(**data)
            except Exception as e:
                self._handle_redis_failure(e)
        
        # In-memory lookup
        latest_data = self._in_memory_store.get(latest_key)
        if latest_data:
            entry = ActionPlanEntry(**latest_data)
            if not entry.is_expired():
                return entry
            else:
                try:
                    del self._in_memory_store[latest_key]
                except KeyError:
                    pass
        
        # In-memory fallback scan
        action_entries = [
            (k, v) for k, v in self._in_memory_store.items()
            if k.startswith(f"blackboard:action_plan:{user_id}:") and not k.endswith(":latest")
        ]
        if not action_entries:
            return None
        
        latest_k, latest_data = sorted(action_entries)[-1]
        entry = ActionPlanEntry(**latest_data)
        if entry.is_expired():
            try:
                del self._in_memory_store[latest_k]
            except KeyError:
                pass
            return None
        return entry

    async def read_action_plan(self, plan_id: str, user_id: str = None) -> Optional[ActionPlanEntry]:
        """Read specific action plan by id"""
        if user_id is None:
            user_id = current_user_id.get()
        key = f"blackboard:action_plan:{user_id}:{plan_id}"
        if self._should_use_redis():
            try:
                data_str = await self._redis_client.get(key)
                self._redis_healthy = True
                if data_str:
                    data = json.loads(data_str)
                    self._in_memory_store[key] = data
                    return ActionPlanEntry(**data)
            except Exception as e:
                self._handle_redis_failure(e)
        
        # In-memory
        data = self._in_memory_store.get(key)
        if data:
            entry = ActionPlanEntry(**data)
            if entry.is_expired():
                try:
                    del self._in_memory_store[key]
                except KeyError:
                    pass
                return None
            return entry
        return None

    async def clear_expired(self) -> None:
        """Periodic cleanup of expired entries (call every 5 minutes)"""
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
                    elif entry_type == "action_plan":
                        entry = ActionPlanEntry(**data)
                    else:
                        continue
                    
                    if entry.is_expired():
                        del self._in_memory_store[key]
                except Exception:
                    pass
            
            log.debug("[BLACKBOARD] Cleanup complete. Entries: %d", len(self._in_memory_store))

    async def get_stats(self) -> Dict[str, int]:
        """Get stats for monitoring"""
        if self._should_use_redis():
            try:
                clinical_count = len(await self._redis_client.keys("blackboard:clinical:*"))
                emotional_count = len(await self._redis_client.keys("blackboard:emotional:*"))
                context_count = len(await self._redis_client.keys("blackboard:context:*"))
                action_count = len(await self._redis_client.keys("blackboard:action_plan:*"))
                self._redis_healthy = True
                return {
                    "clinical": clinical_count,
                    "emotional": emotional_count,
                    "context": context_count,
                    "action_plan": action_count
                }
            except Exception as e:
                self._handle_redis_failure(e)
        
        # In-memory stats
        return {
            "clinical": len([k for k in self._in_memory_store if k.startswith("blackboard:clinical:")]),
            "emotional": len([k for k in self._in_memory_store if k.startswith("blackboard:emotional:")]),
            "context": len([k for k in self._in_memory_store if k.startswith("blackboard:context:")]),
            "action_plan": len([k for k in self._in_memory_store if k.startswith("blackboard:action_plan:")]),
        }

    async def get_active_stress_user_ids(self) -> list[str]:
        """Scan Redis/memory for active stress history keys and extract user UUIDs"""
        pattern = "blackboard:clinical:stress_history:*"
        if self._should_use_redis():
            try:
                keys = await self._redis_client.keys(pattern)
                self._redis_healthy = True
                return [k.split(":")[-1] for k in keys if k]
            except Exception as e:
                self._handle_redis_failure(e)
        
        # In-memory scan
        keys = [k for k in self._in_memory_store.keys() if fnmatch.fnmatch(k, pattern)]
        
        # Filter out expired items in memory
        now = time.time()
        active_users = []
        for k in keys:
            data = self._in_memory_store.get(k)
            if data and now <= data.get("expiry", 0.0):
                active_users.append(k.split(":")[-1])
            elif data:
                try:
                    del self._in_memory_store[k]
                except KeyError:
                    pass
        return active_users

    async def write_value(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Write generic/custom value to Blackboard"""
        now = time.time()
        self._in_memory_store[key] = {
            "value": value,
            "expiry": now + ttl_seconds,
            "l1_expiry": now + 1.0  # Fresh for 1.0s locally
        }
        if self._should_use_redis():
            try:
                await self._redis_client.setex(
                    key,
                    ttl_seconds,
                    json.dumps(value)
                )
                self._redis_healthy = True
            except Exception as e:
                self._handle_redis_failure(e)

    async def read_value(self, key: str) -> Optional[Any]:
        """Read generic/custom value from Blackboard"""
        # Check local L1 cache first
        cached = self._in_memory_store.get(key)
        if cached:
            if time.time() <= cached.get("l1_expiry", 0.0):
                return cached.get("value")

        if self._should_use_redis():
            try:
                data_str = await self._redis_client.get(key)
                self._redis_healthy = True
                if data_str is not None:
                    value = json.loads(data_str)
                    now = time.time()
                    self._in_memory_store[key] = {
                        "value": value,
                        "expiry": now + 300,
                        "l1_expiry": now + 1.0  # L1 cache for 1.0s
                    }
                    return value
            except Exception as e:
                self._handle_redis_failure(e)
        
        # In-memory fallback
        data = self._in_memory_store.get(key)
        if data:
            if time.time() > data.get("expiry", 0.0):
                try:
                    del self._in_memory_store[key]
                except KeyError:
                    pass
                return None
            return data.get("value")
        return None


# Singleton accessor
def get_blackboard() -> BlackboardService:
    """Get or create Blackboard singleton"""
    return BlackboardService()
