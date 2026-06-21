"""
IPScannerUtil — Dynamic IPWebcam Network Discovery & Circuit Breaker

Resolves [Errno 11001] getaddrinfo failures by:
  1. Sweeping the /24 subnet concurrently for :8080/shot.jpg endpoints
  2. Maintaining a circuit-breaker state to avoid flooding on repeated failures
  3. Caching the last known-good IP with a TTL to skip repeat scans
"""

import asyncio
import logging
import os
import socket
import struct
import time
from typing import Optional

import httpx

log = logging.getLogger("hk07.ip_scanner")

# ── Circuit Breaker State (module-level singleton) ────────────────────────────
_CB_OPEN_UNTIL: float = 0.0          # epoch timestamp when breaker resets
_CB_RECOVERY_S: float = 60.0          # reconnect attempt interval - increased to 60s to prevent spamming scans
_LAST_KNOWN_IP: Optional[str] = None  # cached good IP
_LAST_KNOWN_TS: float = 0.0
_IP_CACHE_TTL:  float = 120.0         # seconds to trust cached IP without re-scan

# ── Subshell Route Cache ──────────────────────────────────────────────────────
_ROUTE_CACHE: Optional[tuple[Optional[str], Optional[str]]] = None
_ROUTE_CACHE_TS: float = 0.0
_ROUTE_CACHE_TTL: float = 60.0        # Cache route lookup for 60s


def _cb_is_open() -> bool:
    """Returns True if the circuit breaker is tripped (blocking requests)."""
    return time.monotonic() < _CB_OPEN_UNTIL


def _cb_trip(duration_s: float = _CB_RECOVERY_S) -> None:
    """Trip the circuit breaker for `duration_s` seconds."""
    global _CB_OPEN_UNTIL
    _CB_OPEN_UNTIL = time.monotonic() + duration_s
    log.warning("[IP_SCANNER_CB] Circuit OPEN — retry blocked for %.1fs", duration_s)


def _cb_reset() -> None:
    global _CB_OPEN_UNTIL
    _CB_OPEN_UNTIL = 0.0


# ── Subnet Derivation ─────────────────────────────────────────────────────────

def _derive_subnet_prefix(phone_ip: str) -> str:
    """Derive the /24 prefix from an IP string, e.g. '192.168.205.243' → '192.168.205'."""
    parts = phone_ip.rsplit(".", 1)
    return parts[0] if len(parts) == 2 else phone_ip


def get_default_route_info() -> tuple[Optional[str], Optional[str]]:
    """
    Returns (default_gateway_ip, local_interface_ip) for the active default route.
    Supports Windows and Linux/WSL. Caches result for 60 seconds to avoid subshell overhead.
    """
    global _ROUTE_CACHE, _ROUTE_CACHE_TS
    now = time.monotonic()
    if _ROUTE_CACHE is not None and (now - _ROUTE_CACHE_TS) < _ROUTE_CACHE_TTL:
        return _ROUTE_CACHE

    res = _uncached_get_default_route_info()
    _ROUTE_CACHE = res
    _ROUTE_CACHE_TS = now
    return res


def _uncached_get_default_route_info() -> tuple[Optional[str], Optional[str]]:
    import platform
    import subprocess
    import re

    # 1. Try Windows route print
    if platform.system() == "Windows":
        try:
            out = subprocess.check_output("route print", shell=True, text=True)
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 4 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    gw = parts[2]
                    iface = parts[3]
                    ip_re = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
                    if re.match(ip_re, gw) and gw != "0.0.0.0" and re.match(ip_re, iface):
                        return gw, iface
        except Exception:
            pass

    # 2. Try Linux /proc/net/route
    try:
        gateway = None
        iface_name = None
        with open("/proc/net/route") as fh:
            for line in fh:
                fields = line.strip().split()
                if len(fields) > 2 and fields[1] == "00000000":
                    gateway = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
                    iface_name = fields[0]
                    break
        if gateway and iface_name:
            # Try to get local IP of this interface
            try:
                import fcntl
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                local_ip = socket.inet_ntoa(
                    fcntl.ioctl(
                        s.fileno(),
                        0x8915,  # SIOCGIFADDR
                        struct.pack('256s', iface_name[:15].encode('utf-8'))
                    )[20:24]
                )
                s.close()
                return gateway, local_ip
            except Exception:
                pass
            
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect((gateway, 80))
                local_ip = s.getsockname()[0]
                s.close()
                return gateway, local_ip
            except Exception:
                s.close()
            return gateway, None
    except Exception:
        pass

    return None, None


def _get_physical_interface_ip() -> Optional[str]:
    """Find a local host IP dynamically matching the active default route interface."""
    _, local_ip = get_default_route_info()
    if local_ip:
        return local_ip
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass
    return None


# ── Async Probe ───────────────────────────────────────────────────────────────

async def _probe_ip(ip: str, port: int = 8080, timeout: float = 0.8, local_ip: Optional[str] = None) -> Optional[str]:
    """
    Non-blocking HTTP probe for IPWebcam snapshot endpoint.
    Explicitly binds to the Windows physical network card range (192.168.205.0/24) if available.
    """
    url = f"http://{ip}:{port}/shot.jpg"
    transport = None
    if local_ip:
        try:
            transport = httpx.AsyncHTTPTransport(local_address=local_ip)
        except Exception as e:
            log.debug("[IP_SCANNER] Failed to bind transport to local address %s: %s", local_ip, e)

    try:
        async with httpx.AsyncClient(transport=transport, timeout=timeout) if transport else httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                log.info("[IP_SCANNER] Live IPWebcam found at: %s (bound to local: %s)", url, local_ip)
                return ip
    except Exception:
        pass
    return None


# ── Main Discovery Entry Point ────────────────────────────────────────────────

async def discover_ipwebcam_ip(
    env_phone_ip: Optional[str] = None,
    port: int = 8080,
    scan_timeout: float = 3.0,
) -> Optional[str]:
    """
    Async IPWebcam IP discovery.
    Prioritizes env_phone_ip if provided. Otherwise scans active local subnets dynamically.
    """
    global _LAST_KNOWN_IP, _LAST_KNOWN_TS

    # Subsumption Architecture: Inhibit background/active subnet sweeps if an emergency or safety alert is active.
    # Safety Tier 0 has absolute priority and should bypass non-essential perception sweeps to avoid thread starvation.
    try:
        from services.blackboard_service import get_blackboard
        bb = get_blackboard()
        safety_tripped = await bb.read_value("safety:tripped")
        vitals_emergency = await bb.read_value("sensor:vitals:emergency")
        if safety_tripped or vitals_emergency:
            log.warning("[IP_SCANNER] ⚠️ Subsumption Inhibit: Safety tripped or Vitals emergency active. Bypassing active subnet sweeps.")
            if _LAST_KNOWN_IP:
                return _LAST_KNOWN_IP
            return None
    except Exception as e:
        log.debug("[IP_SCANNER] Failed to check safety status from blackboard: %s", e)

    # Gate: circuit breaker active — skip re-scan, return cached or None
    if _cb_is_open():
        if _LAST_KNOWN_IP:
            log.debug("[IP_SCANNER_CB] Breaker OPEN — returning cached IP: %s", _LAST_KNOWN_IP)
            return _LAST_KNOWN_IP
        log.debug("[IP_SCANNER_CB] Breaker OPEN — no cached IP, returning None")
        return None

    # Resolve local_ip and gw_ip asynchronously to avoid blocking the event loop
    gw_ip, default_local_ip = await asyncio.to_thread(get_default_route_info)
    local_ip = default_local_ip if default_local_ip else await asyncio.to_thread(_get_physical_interface_ip)

    # Phase 1: Honour cached known-good IP within TTL
    if _LAST_KNOWN_IP and (time.monotonic() - _LAST_KNOWN_TS) < _IP_CACHE_TTL:
        probe = await _probe_ip(_LAST_KNOWN_IP, port, local_ip=local_ip)
        if probe:
            _LAST_KNOWN_TS = time.monotonic()  # refresh TTL
            return probe
        log.warning("[IP_SCANNER] Cached IP %s no longer reachable. Running subnet scan.", _LAST_KNOWN_IP)
        _LAST_KNOWN_IP = None

    # Target primary IP: prioritizes env_phone_ip, then active default gateway, then fallback
    primary = env_phone_ip if env_phone_ip else (gw_ip if gw_ip else "192.168.1.1")
    
    # Try probing primary IP first
    result = await _probe_ip(primary, port, timeout=1.0, local_ip=local_ip)
    if result:
        _LAST_KNOWN_IP = result
        _LAST_KNOWN_TS = time.monotonic()
        _cb_reset()
        return result

    # Dynamic active subnets detection to avoid hardcoding a single subnet sweep range
    local_ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                local_ips.append(ip)
    except Exception:
        pass
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in local_ips and not ip.startswith("127.") and not ip.startswith("169.254."):
            local_ips.append(ip)
    except Exception:
        pass

    subnets = []
    if gw_ip:
        prefix = _derive_subnet_prefix(gw_ip)
        if prefix and prefix not in subnets:
            subnets.append(prefix)

    for ip in local_ips:
        prefix = _derive_subnet_prefix(ip)
        if prefix and prefix not in subnets:
            subnets.append(prefix)
            
    # Default fallback subnets
    if not subnets:
        subnets = ["192.168.1"]

    # Gather sweeping targets across all detected subnets
    sweep = []
    for base_subnet in subnets:
        for i in range(1, 255):
            candidate = f"{base_subnet}.{i}"
            if candidate != primary and candidate not in sweep:
                sweep.append(candidate)

    # Concurrent sweep in batches of 20 to limit fd pressure
    batch_size = 20
    deadline = time.monotonic() + scan_timeout
    for i in range(0, len(sweep), batch_size):
        if time.monotonic() > deadline:
            break
        batch = sweep[i:i + batch_size]
        tasks = [asyncio.create_task(_probe_ip(ip, port, timeout=0.6, local_ip=local_ip)) for ip in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, str) and res:
                _LAST_KNOWN_IP = res
                _LAST_KNOWN_TS = time.monotonic()
                _cb_reset()
                log.info("[IP_SCANNER] Subnet sweep found active IPWebcam at: %s", res)
                return res

    # Phase 3: All phases failed — trip circuit breaker
    log.error("[IP_SCANNER] All discovery phases failed. Tripping circuit breaker for %.1fs.", _CB_RECOVERY_S)
    _cb_trip(_CB_RECOVERY_S)
    return None


# ── Async Non-Blocking Frame Fetcher (asyncio.to_thread wrapper) ──────────────

async def fetch_frame_nonblocking(
    ip: str,
    port: int = 8080,
    timeout: float = 2.0,
) -> Optional[bytes]:
    """
    Wraps the blocking requests.get() inside asyncio.to_thread to ensure
    IPWebcam network latency never freezes the main asyncio event loop.

    Returns: Raw JPEG bytes on success, None on failure.
    """
    import requests  # stdlib-compatible sync fetch isolated in thread

    url = f"http://{ip}:{port}/shot.jpg"

    def _blocking_get() -> Optional[bytes]:
        try:
            resp = requests.get(url, timeout=timeout, stream=False)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
        except Exception as exc:
            log.warning("[FRAME_FETCHER] Sync fetch failed for %s: %s", url, exc)
        return None

    # asyncio.to_thread runs the blocking call in a thread pool — zero event-loop blocking
    return await asyncio.to_thread(_blocking_get)
