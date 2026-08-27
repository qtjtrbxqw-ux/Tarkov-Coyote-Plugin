import asyncio
import time
from dghub import DGHubClient
from config import Config
from memory import MemoryReader
from trigger import TriggerLogic
from mod_client import ModClient

class Plugin:
    @staticmethod
    async def run():
        client = DGHubClient()
        config = Config()
        memory = MemoryReader()
        mod_client = None
        running = True
        found_addr = None
        addr_valid = False
        data_type = 'float'
        scan_done = False
        triggered = False
        last_health = None
        wait_start = None
        use_mod_enabled = config.get("use_mod", True)

        # 配置变更回调
        def on_config_changed(key, value):
            nonlocal scan_done, addr_valid, found_addr, use_mod_enabled, mod_client
            if key in ("addressing_mode", "base_address", "offsets", "use_direct", "aob_pattern", "aob_offset"):
                scan_done = False
                addr_valid = False
                found_addr = None
            if key == "use_mod":
                use_mod_enabled = value
                if value and mod_client is None:
                    port = config.get("mod_port", 8765)
                    mod_client = ModClient(port)
                elif not value and mod_client is not None:
                    asyncio.create_task(mod_client.close())
                    mod_client = None
            if key == "mod_port" and use_mod_enabled:
                if mod_client is not None:
                    asyncio.create_task(mod_client.close())
                mod_client = ModClient(value)

        config.register_callback(on_config_changed)

        try:
            await client.connect()

            manifest = {
                "id": "tarkov_health_monitor",
                "name": "塔科夫血量监控",
                "version": "1.1.0",
                "sdk": "1",
                "entry": "main.py",
                "capabilities": {"startup_check": True},
                "config_schema": [
                    {"section":"🎯 寻址模式","fields":[{"key":"addressing_mode","type":"select","label":"模式","default":"auto_scan","options":[{"value":"manual","label":"手动"},{"value":"aob","label":"AOB"},{"value":"auto_scan","label":"自动扫描"}]}]},
                    {"section":"🔧 手动参数","fields":[{"key":"base_address","type":"text","label":"基址/动态地址","default":"0x792F5734"},{"key":"offsets","type":"text","label":"偏移链(逗号分隔)","default":""},{"key":"use_direct","type":"bool","label":"直接读取","default":False}]},
                    {"section":"🧬 AOB参数","fields":[{"key":"aob_pattern","type":"text","label":"AOB特征码","default":""},{"key":"aob_offset","type":"number","label":"偏移量","default":0}]},
                    {"section":"📊 触发条件","fields":[{"key":"threshold","type":"number","label":"阈值","default":30,"min":1,"max":500},{"key":"strength","type":"percent","label":"固定强度","default":50},{"key":"duration","type":"number","label":"持续(秒)","default":1.5,"min":0.1,"max":10,"step":0.1},{"key":"preset","type":"text","label":"波形预设","default":"CS2-受伤"},{"key":"channel","type":"select","label":"通道","default":"both","options":[{"value":"a","label":"A"},{"value":"b","label":"B"},{"value":"both","label":"双通道"}]}]},
                    {"section":"⚡ 动态强度","fields":[{"key":"use_dynamic","type":"bool","label":"启用动态强度","default":True},{"key":"min_intensity","type":"percent","label":"最小强度","default":20},{"key":"max_intensity","type":"percent","label":"最大强度","default":100},{"key":"max_damage_mapping","type":"number","label":"最大映射伤害","default":50,"min":1,"max":200}]},
                    {"section":"🔄 数据源（SPT Mod）","fields":[{"key":"use_mod","type":"bool","label":"优先使用 Mod 数据","default":True,"description":"启用后通过 SPT Mod 获取血量（更稳定），失败时自动回退到内存读取"},{"key":"mod_port","type":"number","label":"Mod HTTP 端口","default":8765,"min":1024,"max":65535}]}
                ]
            }
            await client.hello(manifest)
            ack = await client.recv()
            if not ack or not ack.get("accepted"):
                await client.log("error", f"握手失败: {ack.get('reason') if ack else '未知'}")
                return
            await client.log("info", "✅ 握手成功")
            await client.log("info", "🔴 塔科夫血量监控 v1.1.0 启动")
            await client.log("info", "🔄 配置热更新已启用")

            # 初始化 Mod 客户端
            if config.get("use_mod"):
                port = config.get("mod_port", 8765)
                mod_client = ModClient(port)
                await client.log("info", f"✅ Mod 数据源已启用 (端口 {port})")
            else:
                await client.log("info", "ℹ️ 使用内存读取模式")

            await client.status("⏳ 初始化...")

            async def main_loop():
                nonlocal running, found_addr, addr_valid, data_type, scan_done, triggered, last_health, wait_start, use_mod_enabled, mod_client
                while running:
                    health = None

                    # 根据开关决定是否使用 Mod 数据
                    if use_mod_enabled and mod_client:
                        info = await mod_client.get_player_info()
                        if info and info.get('player') and info['player'].get('health'):
                            health_data = info['player']['health']
                            health = health_data.get('total')
                            if health is not None:
                                await client.status(f"❤️ {health:.1f} HP [Mod]")
                            else:
                                await client.log("debug", "Mod 返回的数据中没有 total 字段")
                        else:
                            await client.log("debug", "Mod 数据获取失败，回退到内存读取")

                    # 如果 Mod 数据获取失败或未启用，使用内存读取
                    if health is None:
                        if not memory.is_connected():
                            if memory.connect():
                                await client.log("info", f"✅ 已连接游戏 (PID: {memory.pm.process_id})")
                                scan_done = False
                                found_addr = None
                                addr_valid = False
                                last_health = None
                                wait_start = None
                                await client.status("✅ 已连接")
                            else:
                                if wait_start is None:
                                    wait_start = time.time()
                                    await client.log("info", "⏳ 等待游戏启动...")
                                elapsed = time.time() - wait_start
                                remain = max(0, 5 - elapsed)
                                await client.status(f"⏳ 等待... ({remain:.1f}s)")
                                if elapsed >= 5:
                                    await client.log("warning", "⏰ 超时，插件关闭")
                                    await client.status("⏰ 超时退出")
                                    running = False
                                    break
                                await asyncio.sleep(1)
                                continue

                        mode = config.get("addressing_mode")
                        addr = None
                        if mode == "manual":
                            scan_done = True
                            base = int(config.get("base_address"), 16)
                            offsets = MemoryReader.parse_offsets(config.get("offsets"))
                            direct = config.get("use_direct")
                            addr, typ = memory.read_manual(base, offsets, direct)
                            if addr:
                                found_addr = addr
                                data_type = typ or 'float'
                                addr_valid = True
                                await client.status(f"❤️ 手动: {hex(addr)}")
                            else:
                                addr_valid = False
                                await client.status("⚠️ 手动地址无效")
                        elif mode == "aob":
                            pattern = config.get("aob_pattern")
                            offset = config.get("aob_offset")
                            if not pattern:
                                addr_valid = False
                                await client.status("⚠️ AOB为空")
                            elif not scan_done:
                                pat = MemoryReader.parse_aob(pattern)
                                if pat:
                                    found = memory.scan_aob(pat, offset)
                                    if found:
                                        found_addr = found
                                        data_type = 'float'
                                        addr_valid = True
                                        await client.log("info", f"✅ AOB成功: {hex(found)}")
                                        await client.status(f"✅ AOB: {hex(found)}")
                                    else:
                                        await client.log("warning", "⚠️ AOB扫描失败")
                                        addr_valid = False
                                        await client.status("⚠️ AOB失败")
                                scan_done = True
                            addr = found_addr if addr_valid else None
                        elif mode == "auto_scan":
                            if not scan_done:
                                await client.log("info", "🔍 自动扫描中...")
                                await client.status("🔍 扫描中...")
                                found, typ = memory.auto_scan(1, 500, lambda m: asyncio.create_task(client.log("info", m)))
                                if found:
                                    found_addr = found
                                    data_type = typ
                                    addr_valid = True
                                    await client.log("info", f"✅ 扫描成功: {hex(found)} ({typ})")
                                    await client.status(f"✅ 地址: {hex(found)}")
                                else:
                                    await client.log("warning", "⚠️ 扫描失败")
                                    addr_valid = False
                                    await client.status("⚠️ 扫描失败")
                                scan_done = True
                            addr = found_addr if addr_valid else None

                        if addr is None or not addr_valid:
                            await client.status("⚠️ 地址无效")
                            await asyncio.sleep(2)
                            continue

                        health = memory.read_health(addr, data_type)
                        if health is None:
                            await client.status("⚠️ 读取失败")
                            await asyncio.sleep(1)
                            continue

                    # 到这里 health 一定有值
                    if last_health is None or abs(health - last_health) > 0.5:
                        await client.status(f"❤️ {health:.1f} HP")

                    damage = 0
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
                        await client.log("info", f"⚡ 触发! 强度 {intensity}% (血量 {health:.1f})")
                        await client.trigger(intensity, duration, preset, channel, f"血量 {health:.1f}")
                        triggered = True
                    elif health >= threshold:
                        triggered = False

                    last_health = health
                    await asyncio.sleep(config.get("check_interval", 0.15))

            async def message_loop():
                nonlocal running, scan_done, addr_valid, found_addr, use_mod_enabled, mod_client
                while running:
                    data = await client.recv()
                    if data is None:
                        continue
                    op = data.get("op")
                    if op == "config_changed":
                        key = data.get("key")
                        val = data.get("value")
                        config.set(key, val)
                        await client.log("info", f"✅ 配置已更新: {key} = {val}")
                        if key in ("addressing_mode", "base_address", "offsets", "use_direct", "aob_pattern", "aob_offset"):
                            scan_done = False
                            addr_valid = False
                            found_addr = None
                        elif key == "use_mod":
                            use_mod_enabled = val
                            if val and mod_client is None:
                                port = config.get("mod_port", 8765)
                                mod_client = ModClient(port)
                                await client.log("info", f"✅ Mod 数据源已启用 (端口 {port})")
                            elif not val and mod_client is not None:
                                await mod_client.close()
                                mod_client = None
                                await client.log("info", "ℹ️ Mod 数据源已禁用，切换到内存读取")
                        elif key == "mod_port" and use_mod_enabled:
                            if mod_client is not None:
                                await mod_client.close()
                            port = val
                            mod_client = ModClient(port)
                            await client.log("info", f"🔄 Mod 端口已更新为 {port}")
                    elif op == "stop":
                        await client.log("info", "收到停止命令")
                        running = False
                        break
                    elif op == "ping":
                        await client.send({"op": "pong", "t": data.get("t")})

            task_main = asyncio.create_task(main_loop())
            task_msg = asyncio.create_task(message_loop())
            await asyncio.wait([task_main, task_msg], return_when=asyncio.FIRST_COMPLETED)
            running = False
            task_main.cancel()
            task_msg.cancel()
            await client.log("info", "👋 插件已退出")

        except Exception as e:
            print(f"❌ 错误: {e}")
            await client.log("error", str(e))
        finally:
            if mod_client:
                await mod_client.close()
            await client.close()