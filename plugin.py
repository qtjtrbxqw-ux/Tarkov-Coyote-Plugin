#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塔科夫血量监控 · DGHub 外部插件（SDK v1）

数据流：SPT 游戏 → (SPT Mod HTTP | pymem 内存读取) → trigger → DGHub → DG-Lab
协议细节参见 DGHub 插件开发指南（SDK v1）。
"""
import asyncio
import json
import os
import time

from dghub import DGHubClient
from config import Config
from memory import AutoScanEngine, MemoryReader
from trigger import TriggerLogic
from mod_client import ModClient

# 寻址参数变更时需要重新定位地址的键
ADDRESS_KEYS = ("addressing_mode", "base_address", "offsets",
                "use_direct", "aob_pattern", "aob_offset")

# AOB / 自动扫描失败后自动重试的冷却间隔（秒）
SCAN_RETRY_DELAY = 10.0
# 自动扫描进入“等待掉血”阶段后，差分轮询的间隔（秒）
AUTO_POLL_DELAY = 5.0
# Mod 数据源持续失败时的轮询冷却（秒），避免 HTTP 空转与日志刷屏
MOD_FAIL_COOLDOWN = 5.0
# 握手后等待主程序推送初始配置的最长时间（秒）；超时则用默认配置继续
CONFIG_WAIT_TIMEOUT = 3.0

# 启动检查步骤顺序
SC_STEPS = ("plugin", "source", "address")
SC_TITLES = {
    "plugin": "连接 DGHub",
    "source": "数据源",
    "address": "血量地址",
}


def _clean_health(v):
    """Mod 端血量校验：必须为 0~10000 的数值，否则视为无效。"""
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    return fv if 0.0 <= fv <= 10000.0 else None


def _load_manifest():
    """从 manifest.json 读取插件清单，保证与 DGHub 侧的元数据始终一致。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"无法读取插件清单 manifest.json: {e}") from e


class Plugin:
    @staticmethod
    async def run():
        client = DGHubClient()
        config = Config()
        memory = MemoryReader()
        mod_client = None
        running = True

        # 握手后主程序会推送一次全量配置，置位后主循环才按用户配置运行
        config_received = asyncio.Event()
        # 后台任务引用集合，防止 create_task 的任务被垃圾回收
        bg_tasks = set()

        # ---- 寻址状态 ----
        found_addr = None
        addr_valid = False
        addr_mode = None            # 当前地址所属寻址模式，避免切换模式后误用旧地址
        data_type = "float"
        last_scan_attempt = 0.0     # AOB / 自动扫描失败重试冷却起点
        auto_engine = None          # 自动扫描状态机（多轮差分收敛）

        # ---- 监控状态 ----
        triggered = False
        last_health = None
        last_mod_attempt = 0.0
        mod_fail_streak = 0
        use_mod_enabled = bool(config.get("use_mod", True))

        # ---- 启动检查状态（仅状态变化时上报）----
        sc = {k: [SC_TITLES[k], "pending", "初始化中", None] for k in SC_STEPS}
        sc["address"] = [SC_TITLES["address"], "idle", "尚未定位血量地址", None]
        last_sc_sig = None

        def set_sc_state(key, state, detail, hint=None):
            sc[key][1] = state
            sc[key][2] = detail
            sc[key][3] = hint

        async def flush_startup():
            nonlocal last_sc_sig
            steps = []
            for k in SC_STEPS:
                title, state, detail, hint = sc[k]
                step = {"key": k, "title": title, "state": state, "detail": detail}
                if hint:
                    step["hint"] = hint
                steps.append(step)
            sig = repr(steps)
            if sig == last_sc_sig:
                return
            last_sc_sig = sig
            await client.startup_check("塔科夫血量监控 启动检查", steps)

        def spawn_log(level, message):
            """在同步回调（on_config_changed）中异步记录日志。"""
            t = asyncio.create_task(client.log(level, message))
            bg_tasks.add(t)
            t.add_done_callback(bg_tasks.discard)

        def spawn_close(mod):
            """在事件循环中异步关闭旧 Mod 客户端，并保留任务引用。"""
            if mod is None:
                return
            t = asyncio.create_task(mod.close())
            bg_tasks.add(t)
            t.add_done_callback(bg_tasks.discard)

        def make_mod_client(port):
            """创建 Mod 客户端；失败返回 None 并异步记日志。"""
            nonlocal mod_client
            try:
                return ModClient(port)
            except Exception as e:
                spawn_log("error", f"创建 Mod 客户端失败: {e}")
                return None

        # 配置热更新统一回调：副作用集中在此，消息循环只负责取值与日志
        def on_config_changed(key, value):
            nonlocal found_addr, addr_valid, addr_mode, data_type
            nonlocal last_scan_attempt, last_mod_attempt, mod_fail_streak
            nonlocal use_mod_enabled, mod_client, auto_engine
            if key in ADDRESS_KEYS:
                found_addr = None
                addr_valid = False
                addr_mode = None
                auto_engine = None
                last_scan_attempt = 0.0
                set_sc_state("address", "idle", "配置已变更，等待重新寻址")
            elif key == "use_mod":
                use_mod_enabled = bool(value)
                if not use_mod_enabled and mod_client is not None:
                    spawn_close(mod_client)
                    mod_client = None
                elif use_mod_enabled and mod_client is None:
                    mod_client = make_mod_client(config.get("mod_port", 8765))
                last_mod_attempt = 0.0
                mod_fail_streak = 0
                set_sc_state("source", "pending", "数据源配置已变更，等待数据")
            elif key == "mod_port" and use_mod_enabled:
                if mod_client is not None:
                    spawn_close(mod_client)
                mod_client = make_mod_client(value)
                last_mod_attempt = 0.0
                mod_fail_streak = 0
                set_sc_state("source", "pending", "Mod 端口已变更，等待数据")

        config.register_callback(on_config_changed)

        try:
            manifest = _load_manifest()
            name = manifest.get("name", "塔科夫血量监控")
            version = manifest.get("version", "?")

            await client.connect()
            await client.hello(manifest)
            ack = await client.recv()
            if not ack or ack.get("op") != "hello_ack" or not ack.get("accepted"):
                await client.log("error", f"握手失败: {ack.get('reason') if ack else '未知'}")
                return
            set_sc_state("plugin", "ok", "插件进程已连接 DGHub")
            await client.log("info", f"✅ 握手成功 · {name} v{version}")
            await client.status("⏳ 初始化...")

            async def message_loop():
                nonlocal running
                try:
                    while running:
                        data = await client.recv()
                        if data is None:
                            if running:
                                await client.log("warning", "📡 与 DGHub 连接已断开，插件退出")
                            running = False
                            break
                        op = data.get("op")
                        if op == "config":
                            # 握手后主程序推送的全量配置：恢复用户保存的设置
                            cfg = data.get("data") or {}
                            for k, v in cfg.items():
                                config.set(k, v)
                            config_received.set()
                            await client.log("info", f"📥 已加载 {len(cfg)} 项配置")
                            await flush_startup()
                        elif op == "config_changed":
                            key = data.get("key")
                            val = data.get("value")
                            config.set(key, val)  # 副作用统一由 on_config_changed 处理
                            # 针对性日志，方便用户在日志面板确认
                            if key == "use_mod":
                                await client.log("info",
                                                 f"✅ Mod 数据源已{'启用' if val else '禁用'}")
                            elif key == "mod_port" and use_mod_enabled:
                                await client.log("info", f"🔄 Mod 端口已更新为 {val}")
                            else:
                                await client.log("info", f"✅ 配置已更新: {key} = {val}")
                            await flush_startup()
                        elif op == "stop":
                            await client.log("info", "收到停止命令")
                            running = False
                            break
                        elif op == "ping":
                            await client.send({"op": "pong", "t": data.get("t")})
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    await client.log("error", f"消息循环异常: {e}")
                    running = False

            async def main_loop():
                nonlocal running, found_addr, addr_valid, addr_mode, data_type
                nonlocal last_scan_attempt, triggered, last_health
                nonlocal last_mod_attempt, mod_fail_streak, mod_client
                nonlocal auto_engine
                try:
                    # 等待主程序推送保存的配置，避免先用默认值空跑
                    try:
                        await asyncio.wait_for(config_received.wait(),
                                               CONFIG_WAIT_TIMEOUT)
                    except asyncio.TimeoutError:
                        await client.log("debug", "未收到初始配置推送，使用默认配置")

                    last_source = None
                    while running:
                        health = None
                        source_name = None

                        # ---- 数据源 A：SPT Mod（HTTP） ----
                        # 懒创建：config 未到达或未启用时兜底按默认配置创建
                        if use_mod_enabled and mod_client is None:
                            mod_client = make_mod_client(config.get("mod_port", 8765))
                            if mod_client is not None:
                                await client.log("info",
                                                 f"✅ Mod 数据源已启用 (端口 {config.get('mod_port', 8765)})")
                        if use_mod_enabled and mod_client is not None:
                            cooldown = MOD_FAIL_COOLDOWN if mod_fail_streak > 0 else 0.0
                            if time.time() - last_mod_attempt >= cooldown:
                                last_mod_attempt = time.time()
                                info = await mod_client.get_player_info()
                                raw_hp = None
                                if info and isinstance(info.get("player"), dict) \
                                        and isinstance(info["player"].get("health"), dict):
                                    raw_hp = info["player"]["health"].get("total")
                                hp = _clean_health(raw_hp)
                                if hp is not None:
                                    health = hp
                                    source_name = "Mod"
                                    mod_fail_streak = 0
                                    set_sc_state("source", "ok", "SPT Mod 数据源正常")
                                else:
                                    mod_fail_streak += 1
                                    if mod_fail_streak == 1:
                                        await client.log("debug",
                                                         "Mod 数据不可用，回退到内存读取")

                        # ---- 数据源 B：内存读取（回退） ----
                        if health is None:
                            if not memory.is_connected():
                                if memory.connect():
                                    await client.log(
                                        "info",
                                        f"✅ 已连接游戏 (PID: {memory.pm.process_id})")
                                    found_addr = None
                                    addr_valid = False
                                    addr_mode = None
                                    auto_engine = None
                                    last_health = None
                                    if use_mod_enabled and mod_fail_streak > 0:
                                        set_sc_state("source", "warn",
                                                     "SPT Mod 不可用，已回退内存读取",
                                                     "请确认 SPT Mod 已加载")
                                    else:
                                        set_sc_state("source", "ok",
                                                     "内存读取模式（已连接游戏进程）")
                                    await client.status("✅ 已连接")
                                else:
                                    # 用户常先启用插件再启动游戏：不设超时自杀，持续等待
                                    set_sc_state("source", "pending",
                                                 "等待游戏进程启动", "启动 SPT 后自动连接")
                                    await client.log(
                                        "debug",
                                        "游戏未运行，持续等待... (启动 SPT 后自动连接)")
                                    await client.status("⏳ 等待游戏启动...")
                                    await asyncio.sleep(1)
                                    await flush_startup()
                                    continue

                            # 寻址：命中缓存则跳过，否则重新定位
                            mode = config.get("addressing_mode")
                            cached = (addr_valid and addr_mode == mode
                                      and found_addr is not None)
                            if mode == "manual":
                                if not cached:
                                    base_s = str(config.get("base_address") or "").strip()
                                    try:
                                        base = int(base_s, 16)
                                    except ValueError:
                                        addr_valid = False
                                        addr_mode = None
                                        set_sc_state("address", "fail", "基址格式错误",
                                                     "示例：0x792F5734")
                                        await client.status("⚠️ 基址格式错误")
                                        await asyncio.sleep(2)
                                        await flush_startup()
                                        continue
                                    offsets = MemoryReader.parse_offsets(
                                        config.get("offsets"))
                                    if offsets is None:
                                        addr_valid = False
                                        addr_mode = None
                                        set_sc_state("address", "fail",
                                                     "偏移链格式错误", "示例：0x10,0x24")
                                        await client.status("⚠️ 偏移格式错误")
                                        await asyncio.sleep(2)
                                        await flush_startup()
                                        continue
                                    res_addr, typ = memory.read_manual(
                                        base, offsets, config.get("use_direct"))
                                    if res_addr:
                                        found_addr = res_addr
                                        data_type = typ or "float"
                                        addr_valid = True
                                        addr_mode = mode
                                        set_sc_state("address", "ok",
                                                     f"手动地址 {hex(found_addr)}")
                                    else:
                                        addr_valid = False
                                        addr_mode = None
                                        set_sc_state("address", "fail", "手动地址无效",
                                                     "检查基址/偏移或切换寻址模式")
                                        await client.status("⚠️ 手动地址无效")
                                        await asyncio.sleep(2)
                                        await flush_startup()
                                        continue
                            elif mode == "aob":
                                if not cached:
                                    pattern = str(config.get("aob_pattern") or "").strip()
                                    if not pattern:
                                        addr_valid = False
                                        addr_mode = None
                                        set_sc_state("address", "idle",
                                                     "等待填写 AOB 特征码")
                                        await client.status("⚠️ AOB 特征码为空")
                                        await asyncio.sleep(2)
                                        await flush_startup()
                                        continue
                                    if time.time() - last_scan_attempt >= SCAN_RETRY_DELAY:
                                        last_scan_attempt = time.time()
                                        set_sc_state("address", "pending",
                                                     "AOB 扫描中...")
                                        pat = MemoryReader.parse_aob(pattern)
                                        if not pat:
                                            addr_valid = False
                                            addr_mode = None
                                            set_sc_state("address", "fail",
                                                         "AOB 格式错误",
                                                         "每字节两位十六进制，如 48 8B 05 ?? ?? ?? ??")
                                            await client.log(
                                                "warning", "⚠️ AOB 特征码格式错误")
                                        else:
                                            try:
                                                found = memory.scan_aob(
                                                    pat,
                                                    int(config.get("aob_offset") or 0))
                                            except ValueError:
                                                found = None
                                                addr_valid = False
                                                addr_mode = None
                                                set_sc_state("address", "fail",
                                                             "AOB 偏移格式错误")
                                            if found:
                                                found_addr = found
                                                data_type = "float"
                                                addr_valid = True
                                                addr_mode = mode
                                                set_sc_state(
                                                    "address", "ok",
                                                    f"AOB 命中: {hex(found)}")
                                                await client.log(
                                                    "info", f"✅ AOB 命中: {hex(found)}")
                                            else:
                                                addr_valid = False
                                                addr_mode = None
                                                set_sc_state(
                                                    "address", "fail", "AOB 未命中",
                                                    "确认特征码与当前游戏版本匹配")
                                                await client.log(
                                                    "warning",
                                                    "⚠️ AOB 未命中，稍后自动重试")
                                                await client.status("⚠️ AOB 未命中")
                                    # 冷却期内不空转重试
                                    if not addr_valid:
                                        await asyncio.sleep(2)
                                        await flush_startup()
                                        continue
                            elif mode == "auto_scan":
                                if not cached:
                                    now = time.time()
                                    acted = False        # 本轮是否执行了扫描动作
                                    if auto_engine is None:
                                        if now - last_scan_attempt >= SCAN_RETRY_DELAY:
                                            last_scan_attempt = now
                                            auto_engine = AutoScanEngine(
                                                memory, 1.0, 500.0,
                                                cancel=lambda: not running)
                                            acted = True
                                            set_sc_state(
                                                "address", "pending",
                                                "自动扫描内存(区域化 float)...",
                                                "请确保游戏内已出生且当前血量在 1~500")
                                            await client.log(
                                                "info",
                                                "🔍 自动扫描(区域化+纯float+稳定性过滤)...")
                                            await client.status("🔍 扫描中...")
                                            loop = asyncio.get_event_loop()
                                            await loop.run_in_executor(
                                                None, auto_engine.start)
                                            for lvl, msg in auto_engine.drain_logs():
                                                await client.log(lvl, msg)
                                    elif auto_engine.phase == "wait_damage" \
                                            and now - last_scan_attempt >= AUTO_POLL_DELAY:
                                        # 差分阶段：更快轮询捕捉玩家掉血
                                        last_scan_attempt = now
                                        acted = True
                                        set_sc_state("address", "pending",
                                                     "差分确认中(等待掉血)...")
                                        loop = asyncio.get_event_loop()
                                        await loop.run_in_executor(
                                            None, auto_engine.poll)
                                        for lvl, msg in auto_engine.drain_logs():
                                            await client.log(lvl, msg)
                                    elif auto_engine.phase == "failed" \
                                            and now - last_scan_attempt >= SCAN_RETRY_DELAY:
                                        auto_engine = None
                                    # 仅在刚执行过扫描动作时才处理阶段结果（避免重复日志）
                                    if auto_engine is not None and acted:
                                        ph = auto_engine.phase
                                        if ph == "done":
                                            found_addr, typ = auto_engine.result()
                                            if (found_addr
                                                    and config.get("addressing_mode")
                                                    == "auto_scan"):
                                                data_type = typ or "float"
                                                addr_valid = True
                                                addr_mode = mode
                                                set_sc_state(
                                                    "address", "ok",
                                                    f"自动扫描确认: {hex(found_addr)}")
                                                await client.log(
                                                    "info",
                                                    f"✅ 自动扫描确认命中: "
                                                    f"{hex(found_addr)}")
                                            auto_engine = None
                                        elif ph == "failed":
                                            addr_valid = False
                                            addr_mode = None
                                            set_sc_state(
                                                "address", "fail",
                                                auto_engine.detail
                                                or "自动扫描未找到血量",
                                                "可改用手动/AOB 寻址")
                                            await client.log(
                                                "warning",
                                                f"⚠️ 自动扫描: {auto_engine.detail}")
                                            await client.status("⚠️ 自动扫描失败")
                                            await asyncio.sleep(2)
                                            await flush_startup()
                                            continue
                                        elif ph == "cancelled":
                                            addr_valid = False
                                            addr_mode = None
                                            auto_engine = None
                                        elif ph == "wait_damage":
                                            n = auto_engine.count
                                            set_sc_state(
                                                "address", "pending",
                                                f"候选 {n}，等待受伤差分确认",
                                                "被打掉血后自动收窄;长时间无结果请改手动/AOB")
                                            await client.log(
                                                "info",
                                                f"🎯 {auto_engine.detail}；"
                                                "请受一次伤(勿立刻治疗)以自动收窄")
                                            await client.status(
                                                f"🎯 候选 {n}，受伤后自动复查...")
                                if not addr_valid:
                                    await asyncio.sleep(2)
                                    await flush_startup()
                                    continue
                            else:
                                # 未知寻址模式
                                addr_valid = False
                                addr_mode = None
                                await client.status("⚠️ 未知寻址模式")
                                await asyncio.sleep(2)
                                await flush_startup()
                                continue

                            addr = (found_addr
                                    if (addr_valid and addr_mode == mode) else None)
                            health = memory.read_health(addr, data_type)
                            if health is None:
                                addr_valid = False
                                addr_mode = None
                                auto_engine = None
                                set_sc_state("address", "warn",
                                             "血量地址失效，重新寻址中")
                                await client.status("⚠️ 读取失败，重新寻址")
                                await asyncio.sleep(1)
                                await flush_startup()
                                continue

                        # ---- 状态栏（血量变化或数据源切换时刷新） ----
                        if source_name is None:
                            source_name = "内存"
                        if (last_health is None
                                or abs(health - last_health) > 0.5
                                or source_name != last_source):
                            await client.status(f"❤️ {health:.1f} HP [{source_name}]")
                        last_source = source_name

                        # ---- 受伤检测与触发 ----
                        damage = 0.0
                        if last_health is not None and health < last_health:
                            damage = last_health - health
                            if damage > 0.5:
                                await client.log("info", f"💥 受伤 -{damage:.1f} HP")

                        threshold = config.get("threshold")
                        if TriggerLogic.should_trigger(health, threshold, triggered):
                            intensity = TriggerLogic.calculate_intensity(damage, config)
                            duration = config.get("duration")
                            preset = config.get("preset")
                            channel = config.get("channel")
                            await client.log(
                                "info",
                                f"⚡ 触发! 强度 {intensity}% (血量 {health:.1f})")
                            await client.trigger(intensity, duration, preset, channel,
                                                 f"血量 {health:.1f}")
                            triggered = True
                        elif health >= threshold:
                            triggered = False

                        last_health = health
                        await flush_startup()
                        await asyncio.sleep(config.get("check_interval", 0.15))
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    await client.log("error", f"监控循环异常: {e}")
                    running = False

            task_main = asyncio.create_task(main_loop())
            task_msg = asyncio.create_task(message_loop())
            await asyncio.wait([task_main, task_msg],
                               return_when=asyncio.FIRST_COMPLETED)
            running = False
            task_main.cancel()
            task_msg.cancel()
            await client.log("info", "👋 插件已退出")
        except Exception as e:
            print(f"❌ 错误: {e}")
            try:
                await client.log("error", str(e))
            except Exception:
                pass
        finally:
            if mod_client is not None:
                try:
                    await mod_client.close()
                except Exception:
                    pass
            try:
                await client.close()
            except Exception:
                pass
