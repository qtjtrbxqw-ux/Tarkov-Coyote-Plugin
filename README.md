<p align="center">
  <img src="https://img.shields.io/badge/status-stable-brightgreen?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/version-2.1.0-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/DGHub-SDK%20v1-orange?style=for-the-badge" alt="DGHub SDK">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows-9cf?style=for-the-badge" alt="Platform">
</p>

# 🔴 Tarkov Health Monitor

> **实时血量监控插件 · 为《逃离塔科夫》离线版 (SPT) 定制**  
> *低延迟 · 免 CE 自动寻址 · 动态伤害强度 · Mod 双数据源 · 热更新 · 无缝 DGHub 集成*

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

它通过直接读取游戏进程内存中的玩家生命值（或优先经配套 SPT Mod 获取），在血量低于设定阈值时，自动通过 DGHub 触发 DG-LAB 郊狼设备反馈，实现**伤害感知的沉浸式体验**。

**v2.1.0 全新寻址内核**：内置**免 CE 自动扫描**——区域化扫描（只遍历可读可写内存）→ 4 字节对齐 + 纯 float 初筛 → 稳定性过滤 → 多轮掉血差分收敛，进对局即可自动定位血量，全程无需手动找地址；配合配套 SPT Mod 数据源（反射读取，跨版本容错），双通道互为备份。

> ✅ 适用于 SPT 3.x / 4.x 全版本  
> ✅ 零侵入 · 不修改游戏文件  
> ✅ 免 CE 自动扫描（默认）/ 手动偏移 / AOB 三模式寻址  
> ✅ 配套 SPT Mod（TarkovCoyoteSptHealthMod）双通道，Mod 不可用时自动回退内存  
> ✅ 所有配置支持热更新，修改后即时生效

---

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| ⚡ **超低延迟** | < 100ms 的读取响应，实时反馈 |
| 🧠 **免 CE 自动寻址** | 自动扫描（默认）/ 手动偏移链 / AOB，进图自动定位血量 |
| 📊 **动态伤害强度** | 根据受到的伤害值自动调整反馈强度 |
| 🔁 **自动重连** | 游戏崩溃后自动恢复连接，无需人工干预 |
| 🎛️ **配置热更新** | 所有参数通过 DGHub 界面实时调整，无需重启 |
| 📡 **事件驱动触发** | 基于 `trigger` 协议，完整支持强度+波形+回退机制 |
| 📊 **状态可视化** | 实时显示血量，支持 DGHub 启动检查面板 |
| 🔄 **Mod 双数据源** | 配套反射读取 Mod，血量更稳、版本容错，失败自动回退内存 |

---

## 🚀 快速开始

### 前置条件
- Windows 10/11
- DGHub 已运行并配对郊狼设备
- 塔科夫离线版 (SPT-AKI) 已启动

### 安装插件
1. 下载最新 ZIP 包（成品包内含 `tarkov_health_monitor_v2.1.0.zip`）
2. DGHub → 插件中心 → 外部插件 → 导入 zip
3. 启用插件 → 配置参数 → 开始监控

> 💡 无需额外安装 Python 环境（已内置 vendor 支持）

### 安装配套 SPT Mod（可选，推荐）
Mod 数据源走游戏内反射读取，血量更稳定且不依赖内存偏移，装好即自动双通道：

1. 将编译好的 `TarkovCoyoteSptHealthMod.dll` 放入 `<SPT>\BepInEx\plugins\`（本机示例：`D:\ZZAXSSA\EFT\BepInEx\plugins\`）
2. 重启游戏进入对局
3. 插件中开启"优先使用 Mod 数据"（默认开启，端口 8765）

> 💡 Mod 源码位于与插件相邻的 `Tarkov-Coyote-SPT-Mod` 工程（`GameStateReader.cs` 以候选名列表做跨版本容错，游戏大版本改名只需追加字段名后重新编译）。Mod 未安装或处于主菜单时，插件自动回退内存读取，无需干预。

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

### 数据源（v2.1.0，配套 Mod 已就绪）

| 字段 | 说明 | 默认 |
|------|------|------|
| `优先使用 Mod 数据` | 通过 SPT Mod 获取血量（更稳定） | `true` |
| `Mod HTTP 端口` | 与 Mod 通信的端口 | `8765` |

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
3. 右键地址 → "找出是什么改写了这个地址" → 回游戏改血量 → 记录偏移量和寄存器值
4. 扫描寄存器值 → 找到绿色基址
5. 填入插件 → 关闭"使用直接地址"

### 方式 B：直接地址（临时，仅限当前会话）
1. 同方式 A 前两步，找到当前血量的动态地址（黑色）
2. 填入插件 → 开启"使用直接地址"
> ⚠️ 游戏重启后地址会变化，需重新操作

### 方式 C：自动扫描（默认，免 CE）
寻址模式选"自动扫描"，插件会：
1. **区域化扫描**：只遍历可读可写的已提交内存（跳过代码段/只读资源），
   按 4 字节对齐初筛落在 1~500 的 **float 值**（血量必然是 float）
2. **稳定性过滤**：间隔二次读取，剔除瞬时抖动/越界的伪候选
3. **多轮掉血差分收敛**：等待你被打后，自动只保留"同步掉血"的地址；
   血量镜像会一起掉血，经 1~3 次受伤事件后收窄到最终地址

> 💡 使用要点：
> - 请在**游戏内已出生**、当前血量在 1~500 时开启（开局后等几秒再启用）
> - 首轮扫描可能耗时数十秒，日志会持续显示进度（候选数量逐步收窄）
> - 提示"等待受伤差分确认"时，**主动受一次伤且别立刻治疗**，插件会在数秒内自动复查收窄
> - 若开着 SPT Mod 数据源且 Mod 正常，插件直接走 Mod 通道，无需内存扫描

---

## ❓ FAQ

<details>
<summary><b>插件启用后一直显示"等待游戏启动"</b></summary>
确保游戏已运行，进程名为 <code>EscapeFromTarkov.exe</code>。若使用自定义 exe，请修改 <code>main.py</code> 中的进程名。
</details>

<details>
<summary><b>一直显示"读取失败"</b></summary>
检查地址和偏移是否正确，或切换"直接地址"模式测试。若使用临时地址，确认游戏重启后已更新。
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
<summary><b>自动扫描一直不收敛 / 候选很多怎么办？</b></summary>
自动扫描需要"掉血事件"来收敛。请在游戏内受一次伤（勿立刻治疗），插件每 5 秒自动复查一次，会把没有掉血的候选剔除；重复 1~3 次受伤即可命中。若长时间无掉血事件（例如在安全区挂机），插件会提示失败，可受一次伤后自动重扫，或改用手动/AOB 寻址。
</details>

<details>
<summary><b>动态强度怎么用？</b></summary>
开启"启用动态伤害强度"后，插件会自动根据受到的伤害值计算强度。伤害越高，强度越大。可在配置中调整最小/最大强度及映射范围。
</details>

<details>
<summary><b>Mod 数据源是什么？</b></summary>
通过配套的 SPT Mod（TarkovCoyoteSptHealthMod）获取血量数据：Mod 在游戏内反射读取血量并经本地 HTTP（127.0.0.1:8765，默认）暴露 /playerinfo、/status 两个接口，插件优先使用 Mod 数据，失败（如主菜单/未装 Mod）时自动回退到内存读取。
</details>

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
