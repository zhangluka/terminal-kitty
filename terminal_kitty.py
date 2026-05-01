#!/usr/bin/env python3
"""
Terminal Kitty — 终端猫咪守护者
当你连续工作太久时，猫咪会来提醒你休息。

活动检测方案：通过 Claude Code 的 hook 事件（UserPromptSubmit / Stop）
写入活动时间戳，守护进程读取时间戳判断活跃度。
也支持独立运行模式（手动计时）。
"""

import json
import os
import sys
import time
import signal
import argparse
from pathlib import Path

# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────

DEFAULT_CONFIG = {
    "enabled": True,
    "thresholds": {
        "gentle": 55,    # 第1档：轻量提醒（分钟）
        "warning": 60,   # 第2档：标准提醒
        "force": 70      # 第3档：强制休息
    },
    "cooldown": 5,       # 休息确认后冷却时间（分钟）
    "check_interval": 30, # 活动检测间隔（秒）
    "idle_timeout": 120,  # 超过此秒数无活动则暂停计时（秒）
    "mood_interval_min": 10,  # 随机卖萌最小间隔（分钟）
    "mood_interval_max": 25   # 随机卖萌最大间隔（分钟）
}

CONFIG_DIR = Path.home() / ".terminal-kitty"
CONFIG_FILE = CONFIG_DIR / "config.json"
PID_FILE = CONFIG_DIR / "terminal-kitty.pid"
ACTIVITY_FILE = CONFIG_DIR / "activity.json"
REMINDER_FILE = CONFIG_DIR / "reminder.txt"
STATE_FILE = CONFIG_DIR / "state.json"


def load_config():
    """加载配置，不存在则创建默认配置"""
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        # 合并默认值（处理新增字段）
        for key, val in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = val
            elif isinstance(val, dict):
                for k, v in val.items():
                    if k not in config[key]:
                        config[key][k] = v
        return config
    except (json.JSONDecodeError, IOError):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存配置到文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────
# 活动检测（基于 hook 事件通知）
# ──────────────────────────────────────────────

def ping_activity():
    """记录活动时间戳（由 hook 调用）"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"timestamp": time.time()}
    with open(ACTIVITY_FILE, "w") as f:
        json.dump(data, f)


def get_last_activity_time():
    """获取最后活动时间戳"""
    try:
        with open(ACTIVITY_FILE, "r") as f:
            data = json.load(f)
        return data.get("timestamp", 0)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return 0


# ──────────────────────────────────────────────
# 提醒文件管理（守护进程写入，hook 读取显示）
# ──────────────────────────────────────────────

def write_reminder(text):
    """守护进程写入提醒到文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(REMINDER_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def check_and_print_reminder():
    """检查并显示提醒或播放动画（由 hook 调用），返回是否有内容"""
    # 先检查普通提醒
    try:
        with open(REMINDER_FILE, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            print(text, flush=True)
            with open(REMINDER_FILE, "w") as f:
                f.write("")
            return True
    except (FileNotFoundError, IOError):
        pass

    return False


# ──────────────────────────────────────────────
# 守护进程状态持久化（支持冷却跨重启）
# ──────────────────────────────────────────────

def save_state(state):
    """保存守护进程状态"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def load_state():
    """加载守护进程状态"""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return {"elapsed_seconds": 0, "current_tier": 0, "in_cooldown": False, "cooldown_until": 0}


# ──────────────────────────────────────────────
# ASCII 猫咪素材
# ──────────────────────────────────────────────

CAT_GENTLE = """
🐱 喵~ 已经{minutes}分钟了，快到休息时间了哦
"""

CAT_WARNING = """
🐱 喵~ 你已经连续工作{minutes}分钟了！
   /\\_/\\
  ( o.o )
   > ^ <  💤

站起来伸个懒腰吧，就像我这样~
"""

CAT_FORCE = """
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
║     你已经连续工作 {minutes} 分钟了               ║
║     起来走动 5 分钟再回来                         ║
║                                                  ║
║     [按 Enter 解放猫咪]                          ║
║                                                  ║
╚══════════════════════════════════════════════════╝
"""

CAT_COOLDOWN = """
🐱 猫咪满意地走开了~ 计时器已重置，继续加油！🎉
"""


# ──────────────────────────────────────────────
# 猫咪随机行为（卖萌用）
# ──────────────────────────────────────────────

import random

CAT_MOODS = [
    ("伸了个大大的懒腰", "  /\\_/\\  ah~\n ( ^.^ )\n  > ω < /"),
    ("舔舔爪子，梳理毛发", "  /\\_/\\\n ( ·.· )~~🐾\n  > ω < ✨"),
    ("追着尾巴转了一圈", "  /\\_/\\\n ( ^.^ )~gotcha!\n  > ω <"),
    ("打了个小盹", "  /\\_/\\\n ( -.- ) 💤\n  > ^ < zzz"),
    ("蹭了蹭你的手", "  /\\_/\\\n ( ^.^ )~~♡\n  > ω < purrr~"),
    ("扑向一个纸团", "  /\\_/\\\n ( ^.^ ) 📄\n  > ω < gotcha!"),
    ("翻了个身，露出肚皮", "   /\\   /\\\n  ( ^.^ )\n ( ⊙ ⊙ ) 摸摸？"),
    ("在键盘旁边踩奶", "  /\\_/\\\n ( ^.^ )♪♡\n  > ω < knead knead~"),
    ("突然竖起耳朵，又趴下了", "  /|_|\\\n ( o.o ) ？！\n  > ^ <"),
    ("扑向自己的影子", "  /\\_/\\\n ( >.< )→ ●\n  > ^ < 抓到了！"),
]


def get_random_mood():
    """随机选一个猫咪行为，返回 (moment, art)"""
    return random.choice(CAT_MOODS)


# ──────────────────────────────────────────────
# 强制模式：阻断终端输入
# ──────────────────────────────────────────────

def force_block():
    """阻断终端，等待用户按 Enter"""
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


# ──────────────────────────────────────────────
# PID 文件管理
# ──────────────────────────────────────────────

def write_pid():
    """写入 PID 文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_pid():
    """删除 PID 文件"""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def is_running():
    """检查是否已有实例在运行"""
    if not PID_FILE.exists():
        return False
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        # 检查进程是否存在
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ValueError, ProcessLookupError):
        return False


# ──────────────────────────────────────────────
# 主循环
# ──────────────────────────────────────────────

def run_daemon(config):
    """守护进程主循环"""
    write_pid()

    # 信号处理：优雅退出
    def cleanup(signum, frame):
        remove_pid()
        save_state({"elapsed_seconds": 0, "current_tier": 0, "in_cooldown": False, "cooldown_until": 0})
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    thresholds = config["thresholds"]
    check_interval = config["check_interval"]
    cooldown_minutes = config["cooldown"]
    idle_timeout = config.get("idle_timeout", 120)
    mood_interval_min = config.get("mood_interval_min", 10) * 60  # 转为秒
    mood_interval_max = config.get("mood_interval_max", 25) * 60

    # 加载上次状态（支持冷却跨重启）
    state = load_state()
    elapsed_seconds = state.get("elapsed_seconds", 0)
    current_tier = state.get("current_tier", 0)
    in_cooldown = state.get("in_cooldown", False)
    cooldown_until = state.get("cooldown_until", 0)
    last_seen_activity = get_last_activity_time()

    # 随机卖萌计时器
    next_mood_time = time.time() + random.randint(int(mood_interval_min), int(mood_interval_max))

    try:
        while True:
            time.sleep(check_interval)

            # 冷却期检查
            if in_cooldown:
                if time.time() >= cooldown_until:
                    in_cooldown = False
                    elapsed_seconds = 0
                    current_tier = 0
                    last_seen_activity = get_last_activity_time()
                continue

            # 检测活动（通过活动文件）
            current_activity = get_last_activity_time()

            if current_activity > last_seen_activity:
                # 有新活动，推进计时器
                elapsed_seconds += check_interval
                last_seen_activity = current_activity
            else:
                # 无新活动，检查是否超过空闲超时
                idle_seconds = time.time() - last_seen_activity if last_seen_activity > 0 else 0
                if idle_seconds > idle_timeout:
                    # 超过空闲超时，暂停计时（但不重置）
                    pass
                else:
                    # 空闲但未超时，仍然推进计时
                    elapsed_seconds += check_interval

            elapsed_minutes = elapsed_seconds / 60

            # 判断档位
            new_tier = 0
            if elapsed_minutes >= thresholds["force"]:
                new_tier = 3
            elif elapsed_minutes >= thresholds["warning"]:
                new_tier = 2
            elif elapsed_minutes >= thresholds["gentle"]:
                new_tier = 1

            # 档位变化时，写入提醒文件（由 hook 读取并显示）
            if new_tier > current_tier:
                current_tier = new_tier

                if current_tier == 1:
                    write_reminder(CAT_GENTLE.format(minutes=int(elapsed_minutes)))
                elif current_tier == 2:
                    write_reminder(CAT_WARNING.format(minutes=int(elapsed_minutes)))
                elif current_tier == 3:
                    write_reminder(CAT_FORCE.format(minutes=int(elapsed_minutes)))
                    # 第3档：写入提醒后进入冷却
                    # 等下一次 hook 触发时显示，然后自动进入冷却
                    in_cooldown = True
                    cooldown_until = time.time() + (cooldown_minutes * 60)

            # 随机卖萌（仅在工作中且无提醒时触发）
            if current_tier == 0 and time.time() >= next_mood_time:
                moment, art = get_random_mood()
                write_reminder(f"🐱 *{moment}*\n{art}\n")
                next_mood_time = time.time() + random.randint(int(mood_interval_min), int(mood_interval_max))

            # 持久化状态
            save_state({
                "elapsed_seconds": elapsed_seconds,
                "current_tier": current_tier,
                "in_cooldown": in_cooldown,
                "cooldown_until": cooldown_until
            })

    except KeyboardInterrupt:
        pass
    finally:
        remove_pid()
        save_state({"elapsed_seconds": 0, "current_tier": 0, "in_cooldown": False, "cooldown_until": 0})


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🐱 Terminal Kitty — 终端猫咪守护者",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  terminal-kitty              # 启动守护进程
  terminal-kitty --daemon     # 后台启动（用于 Claude Code hook）
  terminal-kitty --ping       # 记录活动时间戳（由 hook 调用）
  terminal-kitty --status     # 查看当前状态
  terminal-kitty --stop       # 停止守护进程
  terminal-kitty --config     # 查看/编辑配置
        """
    )
    parser.add_argument("--daemon", action="store_true", help="后台守护进程模式")
    parser.add_argument("--ping", action="store_true", help="记录活动时间戳（由 hook 调用）")
    parser.add_argument("--check-reminder", action="store_true", help="检查并显示提醒（由 hook 调用）")
    parser.add_argument("--hook-ping", action="store_true", help="ping + check，有内容时 exit 1 非阻塞通知")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    parser.add_argument("--stop", action="store_true", help="停止守护进程")
    parser.add_argument("--config", action="store_true", help="查看/编辑配置")
    parser.add_argument("--enabled", type=bool, help="启用/禁用")

    args = parser.parse_args()
    config = load_config()

    if args.ping:
        ping_activity()
        return

    if args.check_reminder:
        check_and_print_reminder()
        return

    if args.hook_ping:
        # 供 Claude Code hook 使用：ping + 检查提醒
        # 有内容时输出到 stderr 并 exit 1（非阻塞通知，不会吞掉用户消息）
        ping_activity()
        # 检查普通提醒
        try:
            with open(REMINDER_FILE, "r", encoding="utf-8") as f:
                text = f.read()
            if text.strip():
                print(text, file=sys.stderr, flush=True)
                with open(REMINDER_FILE, "w") as f:
                    f.write("")
                sys.exit(1)
        except (FileNotFoundError, IOError):
            pass
        # 没有内容，正常退出
        return

    if args.stop:
        if PID_FILE.exists():
            try:
                with open(PID_FILE, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"🐱 已停止守护进程 (PID: {pid})")
            except (OSError, ValueError) as e:
                print(f"🐱 停止失败: {e}")
            finally:
                remove_pid()
        else:
            print("🐱 没有运行中的守护进程")
        return

    if args.status:
        if is_running():
            with open(PID_FILE, "r") as f:
                pid = f.read().strip()
            print(f"🐱 守护进程运行中 (PID: {pid})")
        else:
            print("🐱 守护进程未运行")
        return

    if args.config:
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return

    if args.enabled is not None:
        config["enabled"] = args.enabled
        save_config(config)
        print(f"🐱 已{'启用' if args.enabled else '禁用'} Terminal Kitty")
        return

    if not config["enabled"]:
        print("🐱 Terminal Kitty 已禁用，使用 --enabled true 启用")
        return

    if is_running():
        print("🐱 守护进程已在运行中，使用 --stop 先停止")
        return

    run_daemon(config)


if __name__ == "__main__":
    main()
