import re
import struct
import time
from typing import Callable, Dict, List, Optional, Tuple

try:
    import pymem
    import pymem.pattern
    import pymem.memory
except ImportError:
    print("ERROR: pymem not found")
    raise


# ---- Win32 常量（稳定不变，避免依赖 pymem.ressources 内部路径） ----
_MEM_COMMIT = 0x1000
_MEM_PRIVATE = 0x20000
_MEM_MAPPED = 0x40000
_MEM_IMAGE = 0x1000000
_PAGE_NOACCESS = 0x01
_PAGE_READONLY = 0x02
_PAGE_READWRITE = 0x04
_PAGE_WRITECOPY = 0x08
_PAGE_EXECUTE_READ = 0x20
_PAGE_EXECUTE_READWRITE = 0x40
_PAGE_EXECUTE_WRITECOPY = 0x80
_PAGE_GUARD = 0x100


def _writable_region(protect: int) -> bool:
    """是否可读且可写（HP 必然存放在可写内存里）。

    排除 PAGE_NOACCESS / PAGE_GUARD / 只读/纯执行页，可大幅降低噪声。
    """
    if protect & (_PAGE_NOACCESS | _PAGE_GUARD):
        return False
    return bool(protect & (_PAGE_READWRITE | _PAGE_WRITECOPY
                           | _PAGE_EXECUTE_READWRITE | _PAGE_EXECUTE_WRITECOPY))


def _decode_f32(raw: Optional[bytes]) -> Optional[float]:
    """按小端解析 4 字节为 float；失败/非有限值返回 None。"""
    if not raw or len(raw) < 4:
        return None
    try:
        v = struct.unpack_from('<f', raw, 0)[0]
    except Exception:
        return None
    if v != v or v in (float('inf'), float('-inf')):   # NaN / inf
        return None
    return v


class MemoryReader:
    def __init__(self, process_name="EscapeFromTarkov.exe"):
        self.process_name = process_name
        self.pm = None
        self.connected = False

    def connect(self):
        try:
            self.pm = pymem.Pymem(self.process_name)
            self.connected = True
            return True
        except:
            self.connected = False
            return False

    def is_connected(self):
        if not self.connected or self.pm is None:
            return False
        try:
            _ = self.pm.process_id
            return True
        except:
            self.connected = False
            return False

    def read_float(self, addr):
        try:
            val = self.pm.read_float(addr)
            return val if 0 <= val <= 10000 else None
        except:
            return None

    def read_int(self, addr):
        try:
            val = self.pm.read_int(addr)
            return val if 0 <= val <= 10000 else None
        except:
            return None

    def read_health(self, addr, typ='float'):
        return self.read_float(addr) if typ == 'float' else self.read_int(addr)

    @staticmethod
    def parse_offsets(s):
        """解析偏移链。

        返回 int 列表；空串/空输入返回 []（无偏移）；
        格式非法返回 None（调用方应提示而非继续解析）。
        """
        if not s:
            return []
        try:
            return [int(x.strip(), 16) if x.strip().startswith('0x') else int(x.strip())
                    for x in s.replace(' ', '').split(',') if x.strip()]
        except ValueError:
            return None

    @staticmethod
    def parse_aob(s):
        """把 Cheat Engine 风格 AOB 特征码转成可搜索的正则字节模式。

        pymem.pattern 的模式是“正则字节流”（官方文档），因此：
        - `??` 表示任意一字节，必须映射为正则 `.`（0x2E），
          不能映射为 `?`（0x3F）——`?` 是正则量词，会让模式语义错乱
        - 普通字节须 re.escape，否则字节值恰为 `.*?+()[]{}^$|\\`
          等元字符时会被正则引擎解释，导致扫描失败或误命中

        返回 bytes 正则模式；输入为空或含非法字节返回 None。
        """
        if not s:
            return None
        parts = s.strip().split()
        out = bytearray()
        for p in parts:
            if p.upper() == '??':
                out.append(0x2E)          # regex 任意一字节 '.'
            else:
                try:
                    b = int(p, 16)
                    if not 0 <= b <= 0xFF:
                        return None
                    out.extend(re.escape(bytes([b])))
                except (ValueError, TypeError):
                    return None
        return bytes(out)

    # ---- 供自动扫描器使用的底层原语（测试时可用子类伪造） ----

    def _raw_read_bytes(self, addr: int, size: int) -> Optional[bytes]:
        """原生读内存，失败返回 None（不抛异常）。"""
        try:
            data = pymem.memory.read_bytes(self.pm.process_handle, addr, size)
        except Exception:
            return None
        return data if data else None

    def _iter_readable_regions(self, start=0x10000, end=0x7FFFFFFF):
        """按 VirtualQueryEx 枚举可读可写的已提交私有/映射内存区域。

        只产出「已提交 + 可读可写 + 非镜像文件」的区域，返回 (base, size)。
        相比整段盲扫：不会触发大量非法读、不扫代码段/只读资源，速度快且噪声小。
        """
        handle = self.pm.process_handle
        addr = start
        while addr < end:
            try:
                mbi = pymem.memory.virtual_query(handle, addr)
            except Exception:
                addr += 0x10000
                continue
            if mbi is None:
                addr += 0x10000
                continue
            base = int(getattr(mbi, "BaseAddress", 0) or 0)
            size = int(getattr(mbi, "RegionSize", 0) or 0)
            state = int(getattr(mbi, "State", 0) or 0)
            protect = int(getattr(mbi, "Protect", 0) or 0)
            typ = int(getattr(mbi, "Type", 0) or 0)
            if size <= 0:
                addr += 0x10000
                continue
            if (state & _MEM_COMMIT) and _writable_region(protect) \
                    and (typ & (_MEM_PRIVATE | _MEM_MAPPED)) \
                    and not (typ & _MEM_IMAGE):
                yield base, size
            addr = base + size

    def read_manual(self, base, offsets, direct):
        if not self.is_connected():
            return None, None
        try:
            if direct:
                addr = base
            else:
                if not offsets:
                    addr = base
                else:
                    a = self.pm.read_int(base)
                    for off in offsets[:-1]:
                        a = self.pm.read_int(a + off)
                    addr = a + offsets[-1]
            if self.read_float(addr) is not None:
                return addr, 'float'
            if self.read_int(addr) is not None:
                return addr, 'int'
            return None, None
        except:
            return None, None

    def scan_aob(self, pattern, offset):
        if not self.is_connected() or not pattern:
            return None
        try:
            addr = pymem.pattern.pattern_scan_all(self.pm.process_handle, pattern, return_multiple=False)
            return addr + offset if addr else None
        except:
            return None

    def auto_scan(self, min_val=1, max_val=500, log_cb=None,
                  expected=None, expected_tol=2.0):
        """兼容性单次扫描入口（一次调用内尽力收敛）。

        - expected 非空：直接按已知血量值匹配，精度极高
        - expected 为空：首轮收敛后仍需掉血差分，无法在单次调用内
          保证收敛，返回 None 并提示（插件应改用 AutoScanEngine 多轮驱动）
        """
        if not self.is_connected():
            return None, None
        engine = AutoScanEngine(self, min_val=min_val, max_val=max_val,
                                log_cb=log_cb)
        engine.start(expected=expected, expected_tol=expected_tol)
        if engine.phase == "done":
            return engine.result()
        if log_cb:
            log_cb("info", f"自动扫描: {engine.detail} (候选 {engine.count})")
        return None, None


class AutoScanEngine:
    """多阶段自动扫描器（状态机）。

    阶段：idle → (start) → wait_damage / done / failed
    设计（比旧版盲扫精确得多）：
    1. 区域化扫描：VirtualQueryEx 只读「已提交 + 可读可写」区域，排除代码段
    2. 对齐 + 纯 float 初筛：4 字节对齐、小端 float、有限值、落在 [min,max]
    3. 稳定性过滤：两次带间隔读取，值抖动/越界的丢弃（杀掉瞬时噪声）
    4. 期望值匹配：若已知当前血量（Mod 可用），候选直接收敛到血量地址
    5. 多轮掉血差分：无期望值时等待玩家掉血——每次轮询只保留「掉血了」的
       候选；血量镜像地址会一起掉血，经 1~3 轮事件后收窄到最终地址
    """

    PHASE_IDLE = "idle"
    PHASE_WAIT = "wait_damage"
    PHASE_DONE = "done"
    PHASE_FAILED = "failed"
    PHASE_CANCELLED = "cancelled"

    def __init__(self, reader: MemoryReader, min_val: float = 1.0,
                 max_val: float = 500.0, log_cb: Optional[Callable] = None,
                 cancel: Optional[Callable] = None,
                 settle: float = 0.25, drift: float = 0.75,
                 max_candidates: int = 20000,
                 chunk_size: int = 1 * 1024 * 1024,
                 progress_mb: int = 128, max_scan_mb: int = 2048,
                 damage_min: float = 1.0, big_hit: float = 8.0,
                 damage_rounds: int = 3, max_mirror: int = 2,
                 expected_tol: float = 2.0, idle_limit: int = 40):
        self._reader = reader
        self._lo = float(min_val)
        self._hi = float(max_val)
        self._log_cb = log_cb
        self._cancel = cancel
        self._settle = settle
        self._drift = drift
        self._max_candidates = int(max_candidates)
        self._chunk = int(chunk_size)
        self._progress_mb = int(progress_mb)
        self._max_scan_mb = int(max_scan_mb)
        self._damage_min = float(damage_min)
        self._big_hit = float(big_hit)
        self._damage_rounds = int(damage_rounds)
        self._max_mirror = int(max_mirror)
        self._expected_tol = float(expected_tol)
        self._idle_limit = int(idle_limit)

        self._logs: List[Tuple[str, str]] = []
        self.phase = self.PHASE_IDLE
        self.detail = ""
        self._cand: Dict[int, float] = {}     # addr -> 最近一次读取值
        self._snap: Dict[int, float] = {}     # 差分基准快照
        self._rounds = 0                      # 已收敛轮数
        self._max_event = 0.0                 # 单次最大掉血量
        self._idle = 0                        # 连续无事件轮询数

    # ---------- 对外只读信息 ----------

    @property
    def count(self) -> int:
        return len(self._cand)

    def result(self) -> Tuple[Optional[int], Optional[str]]:
        if self.phase != self.PHASE_DONE or not self._cand:
            return None, None
        return min(self._cand), "float"

    def summary(self) -> dict:
        return {"phase": self.phase, "candidates": self.count,
                "detail": self.detail, "rounds": self._rounds}

    def drain_logs(self) -> List[Tuple[str, str]]:
        """取走并清空内部日志（插件在事件循环线程里异步上报）。"""
        out = self._logs
        self._logs = []
        return out

    def reset(self):
        self.phase = self.PHASE_IDLE
        self.detail = ""
        self._cand.clear()
        self._snap.clear()
        self._rounds = 0
        self._max_event = 0.0
        self._idle = 0

    # ---------- 内部 ----------

    def _log(self, level: str, msg: str):
        self._logs.append((level, msg))
        if self._log_cb:
            try:
                self._log_cb(level, msg)
            except Exception:
                pass

    def _cancelled(self) -> bool:
        try:
            return bool(self._cancel and self._cancel())
        except Exception:
            return False

    def _read_f32(self, addr: int) -> Optional[float]:
        return _decode_f32(self._reader._raw_read_bytes(addr, 4))

    def _scan_all(self) -> bool:
        """区域化扫描候选并做稳定性过滤。失败/取消返回 False。"""
        self._log("info", "🔍 正在枚举可写内存区域...")
        regions = list(self._reader._iter_readable_regions())
        self._log("info", f"🧩 可写区域 {len(regions)} 个")

        cand: Dict[int, float] = {}
        scanned = 0
        last_mb_log = 0
        for base, size in regions:
            if self._cancelled():
                self.phase = self.PHASE_CANCELLED
                self.detail = "扫描已取消"
                return False
            # 4 字节对齐起点（区域基址通常是页对齐，这里显式保证）
            off = (4 - (base % 4)) % 4
            addr = base + off
            remain = size - off
            while remain > 0:
                take = int(min(self._chunk, remain))
                data = self._reader._raw_read_bytes(addr, take)
                if data:
                    for i in range(0, len(data) - 3, 4):
                        v = struct.unpack_from('<f', data, i)[0]
                        if self._lo <= v <= self._hi:   # NaN/±inf 自动排除
                            cand[addr + i] = v
                scanned += take
                remain -= take
                addr += take
                if self._cancelled():
                    self.phase = self.PHASE_CANCELLED
                    self.detail = "扫描已取消"
                    return False
                mb = scanned // (1024 * 1024)
                if mb >= self._max_scan_mb:
                    self._log("warn", f"⚠️ 已达扫描上限 {self._max_scan_mb} MB，截断")
                    return self._stabilize(cand)
                if mb // self._progress_mb > last_mb_log // self._progress_mb \
                        and mb > 0:
                    last_mb_log = mb
                    self._log("info", f"⏳ 已扫描 {mb} MB, 候选 {len(cand)}")
                if len(cand) >= self._max_candidates:
                    self._log("warn", f"⚠️ 候选已达上限 {self._max_candidates}，"
                                      "请收窄数值范围或改用手动/AOB")
                    return self._stabilize(cand)
        self._log("info", f"📦 扫描完成: {scanned // (1024 * 1024)} MB, "
                          f"候选 {len(cand)}")
        return self._stabilize(cand)

    def _stabilize(self, cand: Dict[int, float]) -> bool:
        """稳定性过滤：间隔后二次读取，抖动/越界/失效的丢弃。"""
        time.sleep(self._settle)
        stable: Dict[int, float] = {}
        for addr, v0 in cand.items():
            if self._cancelled():
                self.phase = self.PHASE_CANCELLED
                self.detail = "扫描已取消"
                return False
            v1 = self._read_f32(addr)
            if v1 is None or not (self._lo <= v1 <= self._hi):
                continue
            if abs(v1 - v0) <= self._drift:
                stable[addr] = v1
        self._log("info", f"🧹 稳定性过滤: {len(cand)} → {len(stable)}")
        self._cand = stable
        return True

    # ---------- 对外阶段驱动 ----------

    def start(self, expected: Optional[float] = None,
              expected_tol: Optional[float] = None):
        """首轮：全量扫描 + 稳定性过滤 + 期望值匹配。"""
        self.reset()
        self.phase = self.PHASE_IDLE
        try:
            if not self._reader.is_connected():
                self.phase = self.PHASE_FAILED
                self.detail = "游戏进程未连接"
                return self.phase, self.summary()
            if not self._scan_all():
                return self.phase, self.summary()
            self._snap = dict(self._cand)
            self._rounds = 0
            self._max_event = 0.0
            self._idle = 0

            if expected is not None:
                tol = expected_tol if expected_tol is not None \
                    else self._expected_tol
                surv = {a: v for a, v in self._cand.items()
                        if abs(v - expected) <= tol}
                self._log("info",
                          f"🎯 期望值匹配({expected}±{tol}): "
                          f"{len(self._cand)} → {len(surv)}")
                self._cand = surv
                self._snap = dict(surv)
            self._finalize_start()
        except Exception as e:
            self.phase = self.PHASE_FAILED
            self.detail = f"扫描异常: {e}"
            self._log("error", self.detail)
        return self.phase, self.summary()

    def _finalize_start(self):
        if not self._cand:
            self.phase = self.PHASE_FAILED
            self.detail = "未找到范围内的 float 候选，请确认游戏内已出生"
            return
        if len(self._cand) == 1:
            self.phase = self.PHASE_DONE
            self.detail = f"唯一候选 {hex(min(self._cand))}"
            return
        if len(self._cand) <= self._max_mirror:
            # 极少数镜像同时命中，直接采用
            self.phase = self.PHASE_DONE
            self.detail = f"候选已收窄至 {len(self._cand)} 个"
            return
        self.phase = self.PHASE_WAIT
        self.detail = (f"首轮候选 {len(self._cand)} 个，"
                       "等待受伤后进行差分确认")

    def poll(self, expected: Optional[float] = None,
             expected_tol: Optional[float] = None):
        """差分轮询：只保留掉血（或匹配期望值）的候选。"""
        if self.phase != self.PHASE_WAIT:
            return self.phase, self.summary()
        try:
            snap = self._snap
            cur: Dict[int, float] = {}
            for addr, old in snap.items():
                v = self._read_f32(addr)
                if v is None or not (self._lo <= v <= self._hi):
                    continue
                cur[addr] = v
            if not cur:
                self.phase = self.PHASE_FAILED
                self.detail = "候选全部失效（阵亡/离开对局/进程退出）"
                return self.phase, self.summary()
            # 丢弃读取失效/越界的候选，避免数量虚高
            for a in [a for a in self._cand if a not in cur]:
                self._cand.pop(a, None)
            if not self._cand:
                self.phase = self.PHASE_FAILED
                self.detail = "候选全部失效（阵亡/离开对局/进程退出）"
                return self.phase, self.summary()

            if expected is not None:
                tol = expected_tol if expected_tol is not None \
                    else self._expected_tol
                surv = {a: v for a, v in cur.items()
                        if abs(v - expected) <= tol}
                if surv:
                    self._cand = surv
                    self._rounds += 1
                    self._idle = 0
                    self.detail = (f"数值匹配当前血量 "
                                   f"({expected:.1f}±{tol})，候选 {len(surv)}")
                else:
                    self._snap = cur
                    self.detail = "数值暂不匹配，继续观察"
            else:
                # 掉血事件：本次读取相对快照下降 >= damage_min 的才保留
                deltas = {a: old - cur[a] for a in cur
                          if old - cur[a] >= self._damage_min}
                if deltas:
                    self._max_event = max(self._max_event,
                                          max(deltas.values()))
                    surv = {a: cur[a] for a in deltas}
                    self._cand = surv
                    self._snap = {a: cur[a] for a in surv}
                    self._rounds += 1
                    self._idle = 0
                    self.detail = (f"第 {self._rounds} 次检测到掉血 "
                                   f"(本次最大 -{max(deltas.values()):.1f})，"
                                   f"候选 {len(surv)}")
                    self._log("info",
                              f"💔 掉血差分第 {self._rounds} 轮: "
                              f"候选收窄至 {len(surv)}")
                else:
                    self._idle += 1
                    self._snap = cur
                    self.detail = "未检测到掉血，继续等待受伤..."
            self._finalize_poll()
        except Exception as e:
            self.phase = self.PHASE_FAILED
            self.detail = f"差分轮询异常: {e}"
            self._log("error", self.detail)
        return self.phase, self.summary()

    def _finalize_poll(self):
        if not self._cand:
            self.phase = self.PHASE_FAILED
            self.detail = "候选已耗尽"
            return
        if len(self._cand) == 1 or len(self._cand) <= self._max_mirror:
            self.phase = self.PHASE_DONE
            self.detail = f"候选已确认: {hex(min(self._cand))}"
            return
        # 至少一次“大掉血”且轮数足够，或轮数达到上限时采用最小地址
        # （血量镜像地址往往并存，取任一镜像都可用于监控）
        if self._rounds >= self._damage_rounds and \
                (self._max_event >= self._big_hit or
                 self._rounds >= self._damage_rounds + 1):
            self.phase = self.PHASE_DONE
            self.detail = (f"多轮掉血一致，采用 {hex(min(self._cand))} "
                           f"(剩余 {len(self._cand)} 个镜像)")
            return
        if self._idle >= self._idle_limit:
            self.phase = self.PHASE_FAILED
            self.detail = ("长时间未检测到受伤事件，自动扫描无法收敛；"
                           "请受一次伤，或改用手动/AOB 寻址")
            return
