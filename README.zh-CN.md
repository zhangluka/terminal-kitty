# 🐱 Terminal Kitty — 终端猫咪守护者

[English](README.md)

当你在终端连续工作太久时，猫咪会来提醒你休息。

灵感来自浏览器插件 [Cat Gatekeeper](https://github.com/tjxj/weibo-cat)。

## 特性

- **智能感知**：自动检测终端活动，不需要手动计时
- **三档递进**：温柔提醒 → ASCII 猫咪 → 终端占领，逐步升级
- **零依赖**：纯 Python 标准库，开箱即用
- **跨平台**：支持 Mac / Linux / Windows
- **可配置**：提醒时间、冷却时间均可自定义

## 快速开始

### 方式一：一键安装（推荐）

```bash
git clone https://github.com/zhangluka/terminal-kitty.git
cd terminal-kitty

# Mac/Linux
./install.sh

# Windows
install.bat
```

安装后重启 Claude Code，Terminal Kitty自动启动。

### 方式二：直接运行

```bash
python3 terminal_kitty.py
```

首次运行会自动创建默认配置。

## 三档提醒

| 档位 | 默认时间 | 行为 | 能否无视 |
|------|---------|------|---------|
| 第1档 | 55 分钟 | 一行轻量提醒 | ✅ |
| 第2档 | 60 分钟 | ASCII 猫咪 + 提醒 | ✅ |
| 第3档 | 70 分钟 | 终端被猫咪占领 | ❌ 必须按 Enter |

### 第1档：温柔提醒
```
🐱 喵~ 已经55分钟了，快到休息时间了哦
```

### 第2档：标准提醒
```
🐱 喵~ 你已经连续工作60分钟了！
   /\_/\
  ( o.o )
   > ^ <  💤

站起来伸个懒腰吧，就像我这样~
```

### 第3档：强制休息
```
╔══════════════════════════════════════════════════╗
║                                                  ║
║          /\\_/\\_                                 ║
║         ( o.o )                                  ║
║          > ^ <  🚨                              ║
║         /|   |\\                                  ║
║        (_|   |_)                                 ║
║                                                  ║
║     ⚠️   你的终端已被猫咪占领！                  ║
║                                                  ║
║     你已经连续工作 70 分钟了                     ║
║     起来走动 5 分钟再回来                        ║
║                                                  ║
║     [按 Enter 解放猫咪]                          ║
║                                                  ║
╚══════════════════════════════════════════════════╝
```

## 命令

```bash
terminal-kitty              # 启动守护进程
terminal-kitty --daemon     # 后台模式（用于 Claude Code hook）
terminal-kitty --ping       # 记录活动时间戳（由 hook 调用）
terminal-kitty --status     # 查看运行状态
terminal-kitty --stop       # 停止守护进程
terminal-kitty --config     # 查看当前配置
```

## 配置

配置文件位于 `~/.terminal-kitty/config.json`：

```json
{
  "enabled": true,
  "thresholds": {
    "gentle": 55,
    "warning": 60,
    "force": 70
  },
  "cooldown": 5,
  "check_interval": 30,
  "idle_timeout": 120
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `enabled` | 是否启用 | `true` |
| `thresholds.gentle` | 第1档提醒时间（分钟） | 55 |
| `thresholds.warning` | 第2档提醒时间（分钟） | 60 |
| `thresholds.force` | 第3档强制时间（分钟） | 70 |
| `cooldown` | 休息后冷却时间（分钟） | 5 |
| `check_interval` | 活动检测间隔（秒） | 30 |
| `idle_timeout` | 超过此秒数无活动则暂停计时 | 120 |

## Claude Code 集成

安装脚本会自动配置 4 个 hooks：

| Hook | 作用 |
|------|------|
| `SessionStart` | 启动守护进程 |
| `UserPromptSubmit` | 用户输入时记录活动 |
| `Stop` | Claude 回复结束时记录活动 |
| `SessionEnd` | 停止守护进程 |

手动配置方法——编辑 `~/.claude/settings.json`：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.terminal-kitty/terminal_kitty.py --daemon &",
            "async": true,
            "timeout": 86400
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.terminal-kitty/terminal_kitty.py --ping"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.terminal-kitty/terminal_kitty.py --ping"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "pkill -f 'terminal_kitty.py --daemon' 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

## 工作原理

1. Claude Code 启动时，`SessionStart` hook 自动启动守护进程
2. 用户每次提交 prompt 或 Claude 回复结束时，对应 hook 调用 `--ping` 记录活动时间戳
3. 守护进程每 30 秒检查活动时间戳，有新活动则推进计时器
4. 超过 `idle_timeout` 秒无活动，暂停计时（说明你离开了一会儿）
5. 达到阈值时，根据档位触发对应提醒
6. 第3档会阻断终端，直到用户确认休息

## 许可证

MIT
