from typing import Any, Dict

DEFAULT_CONFIG = {
    "addressing_mode": "auto_scan",
    "base_address": "0x792F5734",
    "offsets": "",
    "use_direct": False,
    "aob_pattern": "",
    "aob_offset": 0,
    "threshold": 30,
    "strength": 50,
    "duration": 1.5,
    "preset": "CS2-受伤",
    "channel": "both",
    "use_dynamic": True,
    "min_intensity": 20,
    "max_intensity": 100,
    "max_damage_mapping": 50,
    "check_interval": 0.15,
    "use_mod": True,
    "mod_port": 8765
}

class Config:
    def __init__(self):
        self._data = DEFAULT_CONFIG.copy()
        self._callbacks = []

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        for cb in self._callbacks:
            cb(key, value)

    def register_callback(self, callback):
        self._callbacks.append(callback)