import os
import sys

def load_env_file():
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        checks = [
            os.path.join(curr_dir, ".env"),
            os.path.join(curr_dir, "backend", ".env"),
            os.path.join(curr_dir, "source", "backend", ".env"),
            os.path.join(curr_dir, "hk07-agent", ".env"),
            os.path.join(curr_dir, "..", ".env"),
            os.path.join(curr_dir, "..", "..", ".env"),
        ]
        for path in checks:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if "=" in line:
                                key, val = line.split("=", 1)
                                key = key.strip()
                                val = val.strip().strip('"').strip("'")
                                if key:
                                    os.environ[key] = val
                    return
                except Exception:
                    pass
        parent = os.path.dirname(curr_dir)
        if parent == curr_dir:
            break
        curr_dir = parent

def get_default_gateway_ip() -> str:
    try:
        from utils.ip_scanner import get_default_route_info
        gw_ip, _ = get_default_route_info()
        if gw_ip:
            return gw_ip
    except Exception:
        pass
    return "127.0.0.1"

def load_env_and_apply_wsl_routing():
    load_env_file()
    if sys.platform.startswith("win"):
        gateway_ip = get_default_gateway_ip()
        if gateway_ip and gateway_ip != "127.0.0.1":
            os.environ["DEFAULT_GATEWAY"] = gateway_ip
            
            # Override Redis config to route local connections to WSL IP
            redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
            if redis_host in ("127.0.0.1", "localhost"):
                os.environ["REDIS_HOST"] = gateway_ip
            
            redis_url = os.environ.get("REDIS_URL")
            if redis_url and ("127.0.0.1" in redis_url or "localhost" in redis_url):
                os.environ["REDIS_URL"] = redis_url.replace("127.0.0.1", gateway_ip).replace("localhost", gateway_ip)
                
            # Override MQTT broker host
            mqtt_host = os.environ.get("MQTT_BROKER_HOST", "localhost")
            if mqtt_host in ("127.0.0.1", "localhost"):
                os.environ["MQTT_BROKER_HOST"] = gateway_ip
                
            mqtt_url = os.environ.get("MQTT_BROKER_URL")
            if mqtt_url and ("127.0.0.1" in mqtt_url or "localhost" in mqtt_url):
                os.environ["MQTT_BROKER_URL"] = mqtt_url.replace("127.0.0.1", gateway_ip).replace("localhost", gateway_ip)

# Call env loader immediately at import time to populate environment variables
load_env_and_apply_wsl_routing()
