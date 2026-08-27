import json
import websockets
import os
from typing import Dict, Any

class DGHubClient:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.host = os.environ.get("DGHUB_HOST", "127.0.0.1")
        self.port = int(os.environ.get("DGHUB_PORT", "8920"))
        self.token = os.environ.get("DGHUB_TOKEN")

    async def connect(self):
        if not self.token:
            raise ValueError("DGHUB_TOKEN not set")
        uri = f"ws://{self.host}:{self.port}/ws/plugin?token={self.token}"
        self.ws = await websockets.connect(uri)
        self.connected = True
        return self.ws

    async def send(self, data: Dict[str, Any]):
        if self.ws:
            try:
                await self.ws.send(json.dumps(data))
            except Exception:
                pass

    async def recv(self):
        if self.ws:
            try:
                raw = await self.ws.recv()
                return json.loads(raw)
            except Exception:
                return None
        return None

    async def close(self):
        if self.ws:
            await self.ws.close()
            self.connected = False

    async def hello(self, manifest: Dict):
        await self.send({"op": "hello", "token": self.token, "manifest": manifest})

    async def log(self, level: str, msg: str):
        await self.send({"op": "log", "level": level, "message": msg})

    async def status(self, text: str):
        await self.send({"op": "status", "fields": {"display_status": text[:50]}})

    async def trigger(self, delta: int, duration: float, preset: str, channel: str, label: str):
        await self.send({
            "op": "trigger",
            "action": "both",
            "delta_pct": delta,
            "strength_mode": "rollback",
            "duration_s": duration,
            "preset": preset,
            "channel": channel,
            "label": label,
            "username": "塔科夫"
        })