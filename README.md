<p align="center">
  <img src="https://img.shields.io/badge/status-stable-brightgreen?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/version-1.0.5-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/DGHub-SDK%20v1-orange?style=for-the-badge" alt="DGHub SDK">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows-9cf?style=for-the-badge" alt="Platform">
</p>

# 🔴 Tarkov Health Monitor

> **实时血量监控插件 · 为《逃离塔科夫》离线版 (SPT) 定制**  
> *低延迟 · 双模式寻址 · 动态伤害强度 · 无缝 DGHub 集成*

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

**Tarkov Health Monitor** 是一款为 [DGHub](https://github.com/hyperzlib/DG-Lab-Coyote-Game-Hub) 打造的外部插件，专为《逃离塔科夫》离线版（SPT-AKI）设计。

它通过直接读取游戏进程内存中的玩家生命值，在血量低于设定阈值时，自动通过 DGHub 触发 DG-LAB 郊狼设备反馈，实现**伤害感知的沉浸式体验**。

> ✅ 适用于 SPT 3.x / 4.x 全版本（需自行适配偏移）  
> ✅ 零侵入 · 不修改游戏文件 · 纯内存读取

---

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| ⚡ **超低延迟** | < 100ms 的读取响应，实时反馈 |
| 🧠 **双模式寻址** | 基址+偏移链（永久） / 直接地址（临时） |
| 📊 **动态伤害强度** | 根据受到的伤害值自动调整反馈强度 |
| 🔁 **自动重连** | 游戏崩溃后自动恢复连接，无需人工干预 |
| 🎛️ **配置热更新** | 所有参数通过 DGHub 界面实时调整，无需重启 |
| 📡 **事件驱动触发** | 基于 `trigger` 协议，完整支持强度+波形+回退机制 |
| 📊 **状态可视化** | 实时显示血量，支持 DGHub 启动检查面板 |

---

## 🚀 快速开始

### 前置条件
- Windows 10/11
- DGHub 已运行并配对郊狼设备
- 塔科夫离线版 (SPT-AKI) 已启动

### 安装
1. 从 Releases 下载最新 ZIP 包
2. DGHub → 插件中心 → 外部插件 → 导入 zip
3. 启用插件 → 配置参数 → 开始监控

> 💡 无需额外安装 Python 环境（已内置 vendor 支持）

---

## 🧰 配置详解

### 内存地址设置

| 字段 | 说明 | 示例 |
|------|------|------|
| `基址 / 动态地址` | 基址（绿色）或临时地址（黑色） | `0x00601630` |
| `偏移链` | 多级偏移，逗号分隔 | `0x10,0x24` |
| `使用直接地址` | 开启后忽略偏移链，直接读取 | `false` |

### 触发条件

| 字段 | 说明 | 默认 |
|------|------|------|
| `生命阈值` | 低于此值触发脉冲 | `30` |
| `检查间隔` | 内存读取频率（秒） | `0.2s` |

### 反馈参数

| 字段 | 说明 | 默认 |
|------|------|------|
| `启用动态伤害强度` | 开启后根据伤害自动调整强度 | `true` |
| `固定强度增量` | 关闭动态时使用的固定值 | `50%` |
| `最小强度` | 动态模式下最低强度 | `20%` |
| `最大强度` | 动态模式下最高强度 | `100%` |
| `最大映射伤害` | 达到此伤害输出最大强度 | `50 HP` |
| `持续时间` | 波形播放时长 | `1.5s` |
| `波形预设` | DGHub 内置波形 | `CS2-受伤` |
| `通道` | a / b / both | `both` |

### 动态强度示例

| 受到伤害 | 输出强度 |
|----------|----------|
| 5 HP | 28% |
| 15 HP | 44% |
| 30 HP | 68% |
| 50 HP+ | 100% |

---

## 🔍 寻址指南

### 方式 A：基址 + 偏移链（推荐，永久有效）
1. 打开 Cheat Engine，附加 `EscapeFromTarkov.exe`
2. 搜索当前血量（数值类型：Float），反复扫描直到地址唯一
3. 右键地址 → “找出是什么改写了这个地址” → 回游戏改血量 → 记录偏移量和寄存器值
4. 扫描寄存器值 → 找到绿色基址
5. 填入插件 → 关闭“使用直接地址”

### 方式 B：直接地址（临时，仅限当前会话）
1. 同方式 A 前两步，找到当前血量的动态地址（黑色）
2. 填入插件 → 开启“使用直接地址”
> ⚠️ 游戏重启后地址会变化，需重新操作

---

## ❓ FAQ

<details>
<summary><b>插件启用后一直显示“等待游戏启动”</b></summary>
确保游戏已运行，进程名为 <code>EscapeFromTarkov.exe</code>。若使用自定义 exe，请修改 <code>main.py</code> 中的进程名。
</details>

<details>
<summary><b>一直显示“读取失败”</b></summary>
检查地址和偏移是否正确，或切换“直接地址”模式测试。若使用临时地址，确认游戏重启后已更新。
</details>

<details>
<summary><b>触发后设备无反应</b></summary>
确认 DGHub 已连接设备，通道配置一致，并查看 DGHub 日志是否有错误。
</details>

<details>
<summary><b>配置修改后不生效</b></summary>
插件支持热更新，保存后自动生效。若无效，可尝试重新保存或重启插件。
</details>

<details>
<summary><b>动态强度怎么用？</b></summary>
开启“启用动态伤害强度”后，插件会自动根据受到的伤害值计算强度。伤害越高，强度越大。可在配置中调整最小/最大强度及映射范围。
</details>

---

## 🔜 后续计划

- 支持更多游戏事件触发（护甲损坏、骨折、失血等）
- 支持多玩家血量监控
- 可配置波形预设列表

---

## 📄 许可证

[MIT](LICENSE) © 2025 鱼汤

## 🙏 致谢

- [hyperzlib](https://github.com/hyperzlib) – DGHub 开发者
- [DG-LAB](https://www.dg-lab.com/) – 郊狼设备
- SPT 社区所有测试者

<p align="center">
  <b>Made with ❤️ by 鱼汤</b>
</p>
