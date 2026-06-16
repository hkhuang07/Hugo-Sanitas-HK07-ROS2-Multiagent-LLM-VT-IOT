"""
SensorFusionBuffer — Multi-modal Ring Buffer for Perception Agent

Fuses data streams:
  - Camera frame metadata (latest JPEG path or base64 snippet)
  - Wristband vitals (60Hz from MQTT)
  - LiDAR snapshot (from Blackboard / MQTT)

All channels are lock-protected and capped at MAX_FRAMES entries.
Perception Agent reads this buffer to build a unified PerceptionScan.
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Deque

log = logging.getLogger("hk07.sensor_fusion")

MAX_FRAMES = 10          # camera frames to keep
MAX_VITALS  = 60         # vitals samples to keep (1 second @ 60Hz)


# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class CameraFrame:
    timestamp: float = field(default_factory=time.time)
    frame_path: str = ""          # path to latest_frame.jpg on disk
    frame_b64:  str = ""          # optional base64 for in-memory transport
    width:  int = 0
    height: int = 0


@dataclass
class VitalsSample:
    timestamp: float = field(default_factory=time.time)
    heart_rate:        Optional[float] = None
    spo2:              Optional[float] = None
    systolic:          Optional[float] = None
    diastolic:         Optional[float] = None
    body_temperature:  Optional[float] = None
    step_count:        Optional[int]   = None
    alert_level:       str = "NORMAL"


@dataclass
class FusedContext:
    """Snapshot of all sensor streams at a point in time — fed to PerceptionAgent"""
    camera: Optional[CameraFrame]   = None
    vitals: Optional[VitalsSample]  = None
    fusion_ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera": asdict(self.camera) if self.camera else None,
            "vitals": asdict(self.vitals) if self.vitals else None,
            "fusion_ts": self.fusion_ts,
        }


# ─── SensorFusionBuffer ────────────────────────────────────────────────────────

class SensorFusionBuffer:
    """
    Thread-safe ring buffer for multi-modal sensor fusion.
    Singleton pattern — shared between Perception Agent and MQTT processors.
    """

    _instance: Optional["SensorFusionBuffer"] = None
    _lock: asyncio.Lock

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._lock = asyncio.Lock()
        self._camera_buf: Deque[CameraFrame]  = deque(maxlen=MAX_FRAMES)
        self._vitals_buf: Deque[VitalsSample] = deque(maxlen=MAX_VITALS)

        log.info("[FUSION_BUFFER] Initialized (cam=%d, vitals=%d)",
                 MAX_FRAMES, MAX_VITALS)

    # ── Write methods ────────────────────────────────────────────────────────

    async def push_camera(self, frame: CameraFrame) -> None:
        async with self._lock:
            self._camera_buf.append(frame)
            log.debug("[FUSION_BUFFER] Camera frame pushed: %s", frame.frame_path)

    async def push_vitals(self, sample: VitalsSample) -> None:
        async with self._lock:
            self._vitals_buf.append(sample)

    # ── Read methods ─────────────────────────────────────────────────────────

    async def latest_camera(self) -> Optional[CameraFrame]:
        async with self._lock:
            return self._camera_buf[-1] if self._camera_buf else None

    async def latest_vitals(self) -> Optional[VitalsSample]:
        async with self._lock:
            return self._vitals_buf[-1] if self._vitals_buf else None

    async def vitals_window(self, n: int = MAX_VITALS) -> List[VitalsSample]:
        """Return last n vitals samples for HRV / trend analysis"""
        async with self._lock:
            samples = list(self._vitals_buf)
            return samples[-n:] if len(samples) >= n else samples

    async def fused_snapshot(self) -> FusedContext:
        """Build a FusedContext from the most recent readings of all streams"""
        async with self._lock:
            cam   = self._camera_buf[-1] if self._camera_buf else None
            vit   = self._vitals_buf[-1] if self._vitals_buf else None
            return FusedContext(camera=cam, vitals=vit)

    async def stats(self) -> Dict[str, int]:
        async with self._lock:
            return {
                "camera_frames": len(self._camera_buf),
                "vitals_samples": len(self._vitals_buf),
            }


# ─── Singleton Accessor ────────────────────────────────────────────────────────

def get_fusion_buffer() -> SensorFusionBuffer:
    return SensorFusionBuffer()
