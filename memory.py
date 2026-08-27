import struct
import time
from typing import Optional, Tuple

try:
    import pymem
    import pymem.pattern
except ImportError:
    print("ERROR: pymem not found")
    raise

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
        if not s: return []
        return [int(x.strip(), 16) if x.strip().startswith('0x') else int(x.strip())
                for x in s.replace(' ', '').split(',') if x.strip()]

    @staticmethod
    def parse_aob(s):
        if not s: return None
        parts = s.strip().split()
        out = bytearray()
        for p in parts:
            if p.upper() == '??':
                out.append(0x3F)
            else:
                try:
                    out.append(int(p, 16))
                except:
                    return None
        return bytes(out)

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

    def auto_scan(self, min_val=1, max_val=500, log_cb=None):
        if not self.is_connected():
            return None, None
        candidates_f = []
        candidates_i = []
        start = 0x10000
        end = 0x7FFFFFFF
        step = 1024 * 1024
        max_bytes = 80 * 1024 * 1024
        scanned = 0
        cur = start
        while cur < end and scanned < max_bytes:
            try:
                size = min(step, end - cur)
                chunk = self.pm.read_bytes(cur, size)
                if chunk:
                    for i in range(0, len(chunk)-4, 4):
                        try:
                            v = struct.unpack('<f', chunk[i:i+4])[0]
                            if min_val <= v <= max_val:
                                candidates_f.append(cur+i)
                        except: pass
                    for i in range(0, len(chunk)-4, 4):
                        try:
                            v = struct.unpack('<I', chunk[i:i+4])[0]
                            if min_val <= v <= max_val:
                                candidates_i.append(cur+i)
                        except: pass
                scanned += size
                cur += size
                if log_cb and scanned % (10*1024*1024) == 0:
                    log_cb(f"扫描 {scanned//(1024*1024)} MB")
            except:
                cur += step
        for addr in candidates_f[:150]:
            try:
                v1 = self.read_float(addr)
                if not (min_val <= v1 <= max_val): continue
                time.sleep(0.05)
                v2 = self.read_float(addr)
                if min_val <= v2 <= max_val and abs(v2-v1) < 0.5:
                    return addr, 'float'
            except: pass
        for addr in candidates_i[:150]:
            try:
                v1 = self.read_int(addr)
                if not (min_val <= v1 <= max_val): continue
                time.sleep(0.05)
                v2 = self.read_int(addr)
                if min_val <= v2 <= max_val and v1 == v2:
                    return addr, 'int'
            except: pass
        return None, None