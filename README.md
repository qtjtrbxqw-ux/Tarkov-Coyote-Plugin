<p align="center">
  <img src="https://img.shields.io/badge/status-stable-brightgreen?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/version-1.0.4-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/DGHub-SDK%20v1-orange?style=for-the-badge" alt="DGHub SDK">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows-9cf?style=for-the-badge" alt="Platform">
</p>

---

# 🔴 Tarkov Health Monitor

> **Real-time health monitoring plugin for Escape From Tarkov (SPT) via DGHub**  
> *低延迟 · 双模式寻址 · 无缝 DGHub 集成*

<p align="center">
  <b>将游戏伤痛，转化为身体感知。</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.7%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/WebSocket-RFC%206455-1A7F9E?logo=websocket&logoColor=white" alt="WebSocket">
  <img src="https://img.shields.io/badge/Memory-pymem-4B8BBE?logo=memory" alt="pymem">
</p>

---

## 📖 概述

**Tarkov Health Monitor** 是一款为 [DGHub](https://github.com/hyperzlib/DG-Lab-Coyote-Game-Hub) 打造的外部插件，专为《逃离塔科夫》离线版（SPT-AKI）设计。它通过直接读取游戏进程内存中的玩家生命值，在血量低于设定阈值时，自动通过 DGHub 触发 DG-LAB 郊狼设备反馈，实现**伤害感知的沉浸式体验**。

> ✅ 适用于 SPT 3.x / 4.x 全版本（需自行适配偏移）
> ✅ 零侵入 · 不修改游戏文件 · 纯内存读取

---

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| ⚡ **超低延迟** | < 100ms 的读取响应，实时反馈 |
| 🧠 **双模式寻址** | 基址+偏移链（永久） / 直接地址（临时） |
| 🔁 **自动重连** | 游戏崩溃后自动恢复连接，无需人工干预 |
| 🎛️ **配置热更新** | 所有参数通过 DGHub 界面实时调整，无需重启 |
| 📡 **事件驱动触发** | 基于 `trigger` 协议，完整支持强度+波形+回退机制 |
| 📊 **状态可视化** | 实时显示血量，支持 DGHub 启动检查面板 |

---

## 🏗️ 架构原理
