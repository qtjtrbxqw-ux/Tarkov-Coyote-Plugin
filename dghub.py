import json
import os
import websockets
from typing import Dict, Any, Optional

try:
    from websockets.exceptions import ConnectionClosed
except ImportError:  # websockets < 10 兼容
    from websockets import ConnectionClosed

class DGHubClient:
    """DGHub 外部插件 WebSocket 客户端（SDK v1）。

    协议字段的权威定义见 DGHub 插件开发指南（SDK v1）。
    """

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
        if self.ws and self.connected:
            try:
                await self.ws.send(json.dumps(data))
            except Exception:
                self.connected = False

    async def recv(self) -> Optional[Dict[str, Any]]:
        """接收并解析一条消息。

        返回:
            dict  正常 JSON 消息
            {}    无法解析的坏帧（丢弃，不视为断开）
            None  连接已断开（由上层结束循环）
        """
        if not self.ws:
            return None
        try:
            raw = await self.ws.recv()
            return json.loads(raw)
        except ConnectionClosed:
            # 主程序退出 / 网络异常：真正的断开
            self.connected = False
            return None
        except Exception:
            # 非 JSON 坏帧等瞬时错误：忽略该帧，保持连接继续
            return {}

    async def close(self):
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.ws = None
        self.connected = False

    async def hello(self, manifest: Dict):
        await self.send({"op": "hello", "token": self.token, "manifest": manifest})

    async def log(self, level: str, msg: str):
        await self.send({"op": "log", "level": level, "message": msg})

    async def status_fields(self, fields: Dict[str, Any]):
        """上报任意持续状态字段（display_status / startup_check 等）。"""
        await self.send({"op": "status", "fields": fields})

    async def status(self, text: str):
        await self.status_fields({"display_status": text[:50]})

    async def startup_check(self, title: str, steps: list):
        """上报启动检查面板（需 manifest.capabilities.startup_check）。

        steps 每项: {key, title, state, detail, hint?}
        state: idle / pending / ok / warn / fail
        """
        await self.send({
            "op": "status",
            "fields": {"startup_check": {"title": title, "steps": steps}},
        })

    async def trigger(self, delta_pct: int, duration: float, preset: str, channel: str, label: str):
        # delta_pct 为相对 baseline 的增量；本插件从不发 permanent 触发，
        # baseline 恒为 0（除非用户设置了 idle_strength），因此实际等于目标强度。
        await self.send({
            "op": "trigger",
            "action": "both",
            "delta_pct": delta_pct,
            "strength_mode": "rollback",
            "duration_s": duration,
            "preset": preset,
            "channel": channel,
            "label": label,
            "username": "塔科夫",
        })
