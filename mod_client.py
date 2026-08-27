import aiohttp
import asyncio
from typing import Optional, Dict

class ModClient:
    def __init__(self, port=8765):
        self.base_url = f"http://127.0.0.1:{port}"
        self.session = None

    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1.5))

    async def get_player_info(self) -> Optional[Dict]:
        """获取玩家信息（包含血量）"""
        try:
            await self._ensure_session()
            async with self.session.get(f"{self.base_url}/playerinfo") as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return None

    async def get_status(self) -> Optional[str]:
        """获取游戏状态（menu/raid_alive/raid_dead）"""
        try:
            await self._ensure_session()
            async with self.session.get(f"{self.base_url}/status") as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception:
            pass
        return None

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None