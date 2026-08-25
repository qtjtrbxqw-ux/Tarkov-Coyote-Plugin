#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import os
import sys
import time
import websockets
from typing import Optional, List, Dict, Any

try:
    import pymem
except ImportError:
    print("ERROR: pymem 未找到")
    sys.exit(1)

config: Dict[str, Any] = {
    "base_address": "0x792F5734",
    "offsets": "",
    "threshold": 30,
    "check_interval": 0.2,
    "delta_pct": 50,
    "duration_s": 1.5,
    "preset": "CS2-受伤",
    "channel": "both"
}
running = True
pm = None

def parse_offsets(offsets_str: str) -> List[int]:
    if not offsets_str or not offsets_str.strip():
        return []
    parts = offsets_str.replace(" ", "").split(",")
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.startswith("0x") or p.startswith("0X"):
            result.append(int(p, 16))
        else:
            result.append(int(p))
    return result

def read_health(pm_instance, base_addr: int, offsets: List[int]) -> Optional[float]:
    if pm_instance is None:
        return None
    try:
        if not offsets:
            return pm_instance.read_float(base_addr)
        addr = pm_instance.read_int(base_addr)
        for off in offsets[:-1]:
            addr = pm_instance.read_int(addr + off)
        final_addr = addr + offsets[-1]
        return pm_instance.read_float(final_addr)
    except Exception:
        return None

async def send_log(ws, level: str, msg: str):
    if ws:
        await ws.send(json.dumps({"op": "log", "level": level, "message": msg}))

async def send_status(ws, display: str):
    if ws:
        await ws.send(json.dumps({"op": "status", "fields": {"display_status": display[:50]}}))

async def send_trigger(ws, delta_pct, duration_s, preset, channel, label):
    if ws:
        msg = {
            "op": "trigger",
            "action": "both",
            "delta_pct": delta_pct,
            "strength_mode": "rollback",
            "duration_s": duration_s,
            "preset": preset,
            "channel": channel,
            "label": label,
            "username": "塔科夫"
        }
        await ws.send(json.dumps(msg))

async def monitor_loop(ws):
    global config, pm, running
    base_addr = int(config.get("base_address", "0x792F5734"), 16)
    offsets = parse_offsets(config.get("offsets", ""))
    threshold = config.get("threshold", 30)
    interval = config.get("check_interval", 0.2)
    last_health = None
    triggered = False
    await send_log(ws, "info", f"监控启动: 基址={hex(base_addr)}, 偏移={offsets}, 阈值={threshold}")
    
    while running:
        if pm is None:
            try:
                new_pm = pymem.Pymem("EscapeFromTarkov.exe")
                pm = new_pm
                await send_log(ws, "info", f"已连接游戏 (PID: {pm.process_id})")
                await send_status(ws, "❤️ 等待血量...")
            except Exception:
                await send_status(ws, "⏳ 等待游戏启动...")
                await asyncio.sleep(2)
                continue

        health = read_health(pm, base_addr, offsets)
        if health is None:
            await send_status(ws, "⚠️ 读取失败(检查基址)")
            await asyncio.sleep(2)
            continue
        
        if last_health is None or abs(health - last_health) > 0.5:
            await send_status(ws, f"❤️ {health:.1f} HP")
            last_health = health
        
        if health < threshold and not triggered:
            await send_log(ws, "info", f"⚡ 触发！血量 {health:.1f} < {threshold}")
            await send_trigger(
                ws,
                config.get("delta_pct", 50),
                config.get("duration_s", 1.5),
                config.get("preset", "CS2-受伤"),
                config.get("channel", "both"),
                f"血量 {health:.1f}"
            )
            triggered = True
        elif health >= threshold:
            triggered = False
        await asyncio.sleep(interval)

async def handle_messages(ws):
    global config, running
    async for raw in ws:
        try:
            data = json.loads(raw)
            op = data.get("op")
            if op == "config_changed":
                key = data.get("key")
                value = data.get("value")
                if key in config:
                    config[key] = value
                    await send_log(ws, "info", f"配置更新: {key} = {value}")
            elif op == "stop":
                await send_log(ws, "info", "收到 stop 命令")
                running = False
                break
            elif op == "ping":
                await ws.send(json.dumps({"op": "pong", "t": data.get("t")}))
        except json.JSONDecodeError:
            pass

async def main():
    global pm, running
    host = os.environ.get("DGHUB_HOST", "127.0.0.1")
    port = os.environ.get("DGHUB_PORT", "8920")
    token = os.environ.get("DGHUB_TOKEN")
    if not token:
        print("ERROR: DGHUB_TOKEN 未设置")
        sys.exit(1)
    uri = f"ws://{host}:{port}/ws/plugin?token={token}"
    async with websockets.connect(uri) as ws:
        # ★★★ 修复：先握手，再发日志 ★★★
        manifest = {
            "id": "tarkov_health_monitor",
            "name": "塔科夫血量监控",
            "version": "1.0.0",
            "sdk": "1",
            "entry": "main.py",
            "capabilities": {"startup_check": True}
        }
        hello_msg = {"op": "hello", "token": token, "manifest": manifest}
        await ws.send(json.dumps(hello_msg))
        
        ack_raw = await ws.recv()
        ack = json.loads(ack_raw)
        if not ack.get("accepted"):
            print(f"握手拒绝: {ack.get('reason')}")
            return
        print("握手成功")
        
        # 握手成功后，可以安全发送日志了
        await send_log(ws, "info", f"已连接 DGHub: {host}:{port}")
        await send_log(ws, "info", "等待游戏进程 (EscapeFromTarkov.exe)...")
        
        monitor_task = asyncio.create_task(monitor_loop(ws))
        msg_task = asyncio.create_task(handle_messages(ws))
        await asyncio.wait([monitor_task, msg_task], return_when=asyncio.FIRST_COMPLETED)
        monitor_task.cancel()
        msg_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())