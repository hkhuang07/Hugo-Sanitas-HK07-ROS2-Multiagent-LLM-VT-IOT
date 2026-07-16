import asyncio

_device_config = {"phone_ip": "", "camera_port": "8080", "updated_at": 0}
_sensor_cache = {}
_cache_lock = asyncio.Lock()
