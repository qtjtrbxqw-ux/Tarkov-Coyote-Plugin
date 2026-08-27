#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# 优先从 vendor 导入 pymem
vendor_path = os.path.join(os.path.dirname(__file__), "vendor")
if os.path.exists(vendor_path):
    sys.path.insert(0, vendor_path)

from plugin import Plugin
import asyncio

if __name__ == "__main__":
    asyncio.run(Plugin.run())