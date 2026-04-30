# 🐱 Terminal Kitty

[中文](README.zh-CN.md)

A cute terminal companion that reminds you to take breaks when you've been working too long.

Inspired by the browser extension [Cat Gatekeeper](https://github.com/tjxj/weibo-cat).

## Features

- **Smart Detection** — Tracks terminal activity via Claude Code hooks, no manual timer needed
- **Three-Tier Escalation** — Gentle nudge → ASCII cat → Terminal takeover, progressively more insistent
- **Zero Dependencies** — Pure Python standard library, works out of the box
- **Cross-Platform** — Mac / Linux / Windows
- **Configurable** — Thresholds, cooldown, check intervals all customizable

## Quick Start

### Option 1: One-Click Install (Recommended)

```bash
git clone https://github.com/zhangluka/terminal-kitty.git
cd terminal-kitty

# Mac/Linux
./install.sh

# Windows
install.bat
```

Restart Claude Code and Terminal Kitty starts automatically.

### Option 2: Run Directly

```bash
python3 terminal_kitty.py
```

Creates default config on first run.

## Three-Tier Reminder

| Tier | Default Time | Behavior | Can Ignore? |
|------|-------------|----------|-------------|
| 1 | 55 min | One-line gentle reminder | ✅ |
| 2 | 60 min | ASCII cat + reminder | ✅ |
| 3 | 70 min | Terminal taken over by cat | ❌ Must press Enter |

### Tier 1: Gentle Reminder
```
🐱 Meow~ It's been 55 minutes, break time is coming~
```

### Tier 2: Standard Reminder
```
🐱 Meow~ You've been working for 60 minutes!
   /\_/\
  ( o.o )
   > ^ <  💤

Stand up and stretch, just like me~
```

### Tier 3: Forced Break
```
╔══════════════════════════════════════════════════╗
║                                                  ║
║          /\\_/\\_                                 ║
║         ( o.o )                                  ║
║          > ^ <  🚨                              ║
║         /|   |\\                                  ║
║        (_|   |_)                                 ║
║                                                  ║
║     ⚠️   YOUR TERMINAL HAS BEEN TAKEN OVER!     ║
║                                                  ║
║     You've been working for 70 minutes           ║
║     Take a 5-minute walk                         ║
║                                                  ║
║     [Press Enter to free the cat]                ║
║                                                  ║
╚══════════════════════════════════════════════════╝
```

<img width="494" height="345" alt="image" src="https://github.com/user-attachments/assets/01e4b8bb-9c1e-4a06-9793-1325d9afffeb" />


## Commands

```bash
terminal-kitty              # Start daemon
terminal-kitty --daemon     # Background mode (for Claude Code hook)
terminal-kitty --ping       # Record activity timestamp (called by hooks)
terminal-kitty --status     # Check running status
terminal-kitty --stop       # Stop daemon
terminal-kitty --config     # View current config
```

## Configuration

Config file at `~/.terminal-kitty/config.json`:

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

| Field | Description | Default |
|-------|-------------|---------|
| `enabled` | Enable/disable | `true` |
| `thresholds.gentle` | Tier 1 reminder time (min) | 55 |
| `thresholds.warning` | Tier 2 reminder time (min) | 60 |
| `thresholds.force` | Tier 3 force time (min) | 70 |
| `cooldown` | Cooldown after break (min) | 5 |
| `check_interval` | Activity check interval (sec) | 30 |
| `idle_timeout` | Pause timer after this many sec idle | 120 |

## Claude Code Integration

The install script auto-configures 4 hooks:

| Hook | Purpose |
|------|---------|
| `SessionStart` | Start daemon |
| `UserPromptSubmit` | Record activity on user input |
| `Stop` | Record activity when Claude responds |
| `SessionEnd` | Stop daemon |

Manual setup — edit `~/.claude/settings.json`:

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

## How It Works

1. `SessionStart` hook launches the daemon when Claude Code starts
2. Each user prompt or Claude response triggers `--ping` to record activity
3. Daemon checks activity timestamps every 30 seconds; new activity advances the timer
4. No activity for `idle_timeout` seconds pauses the timer (you stepped away)
5. When a threshold is hit, the corresponding tier reminder fires
6. Tier 3 blocks the terminal until the user confirms they'll take a break

## License

MIT
