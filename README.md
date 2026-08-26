<p align="center">
  <img src="https://img.shields.io/badge/status-stable-brightgreen?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/version-1.0.9-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/DGHub-SDK%20v1-orange?style=for-the-badge" alt="DGHub SDK">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows-9cf?style=for-the-badge" alt="Platform">
</p>

# 🔴 Tarkov Health Monitor

> **实时血量监控插件 · 为《逃离塔科夫》离线版 (SPT) 定制**  
> *低延迟 · 三种寻址模式 · 动态伤害强度 · 热更新 · 无缝 DGHub 集成*

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

> ✅ 适用于 SPT 3.x / 4.x 全版本  
> ✅ 零侵入 · 不修改游戏文件 · 纯内存读取  
> ✅ 所有配置支持热更新，修改后即时生效

---

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| ⚡ **超低延迟** | < 100ms 的读取响应，实时反馈 |
| 🧠 **三种寻址模式** | 手动 / AOB特征码 / 全自动扫描 |
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
- **Python 依赖**：插件需要 `pymem` 库。如果压缩包中未包含 `vendor/pymem`，请手动安装：`pip install pymem`

### 安装
1. 从 Releases 下载最新 ZIP 包
2. DGHub → 插件中心 → 外部插件 → 导入 zip
3. 启用插件 → 配置参数 → 开始监控

> 💡 首次使用推荐 **全自动扫描** 模式，无需手动配置地址。

---

## 🧰 三种寻址模式对比

| 模式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **全自动扫描** | 无需任何配置，开箱即用 | 扫描较慢（约10-30秒） | 新手用户 / 快速测试 |
| **AOB特征码** | 速度快，精准可靠 | 需手动获取特征码 | 追求稳定 / 长期使用 |
| **手动模式** | 完全可控 | 需CE查找地址 | 熟悉CE的玩家 |

---

## 🧰 配置详解

### 内存地址设置

| 字段 | 说明 | 示例 |
|------|------|------|
| `寻址模式` | manual / aob / auto_scan | `auto_scan` |
| `基址 / 动态地址` | 手动模式时使用 | `0x00601630` |
| `偏移链` | 手动模式使用 | `0x10,0x24` |
| `使用直接地址` | 手动模式开关 | `false` |
| `特征码 (AOB)` | AOB模式使用 | `89 45 ?? 8B 45` |
| `特征码偏移` | AOB模式使用 | `0x10` |
| `自动扫描最小值` | 自动扫描范围下限 | `1` |
| `自动扫描最大值` | 自动扫描范围上限 | `500` |

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
| `波形预设名称` | DGHub 内置波形名称 | `CS2-受伤` |
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

### 全自动扫描（最简单）

1. 选择 `auto_scan` 模式
2. 启用插件，等待扫描完成（约10-30秒）
3. 日志显示地址即表示成功

### AOB特征码（进阶）

1. 用 Cheat Engine 找到血量地址
2. 在内存浏览器中复制地址附近的唯一字节
3. 用 `??` 替代动态字节
4. 填入插件配置

### 手动模式（熟悉CE）

1. 用 CE 找到基址或临时地址
2. 填入对应字段
3. 选择 `manual` 模式

---

## ❓ FAQ

<details>
<summary><b>全自动扫描失败怎么办？</b></summary>
尝试调整扫描范围（最小值/最大值），或切换到 AOB/手动模式。
</details>

<details>
<summary><b>AOB特征码怎么获取？</b></summary>
用 CE 找到血量地址后，在内存浏览器中复制地址附近的唯一字节序列，用 `??` 替代动态字节。
</details>

<details>
<summary><b>插件启用后一直显示"等待游戏启动"</b></summary>
确保游戏已运行，进程名为 <code>EscapeFromTarkov.exe</code>。
</details>

<details>
<summary><b>触发后设备无反应</b></summary>
确认 DGHub 已连接设备，通道配置一致，查看 DGHub 日志。
</details>

<details>
<summary><b>配置修改后不生效</b></summary>
插件支持热更新，保存后自动生效。
</details>

<details>
<summary><b>提示缺少 pymem 库</b></summary>
请执行 <code>pip install pymem</code>，或将 pymem 目录放入插件根目录的 <code>vendor/</code> 下。
</details>

---

## 🔜 后续计划

- 支持更多游戏事件触发（护甲损坏、骨折、失血等）
- 支持多玩家血量监控
- 优化自动扫描性能

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
