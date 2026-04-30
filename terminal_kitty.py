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
    "idle_timeout": 120   # 超过此秒数无活动则暂停计时（秒）
}

CONFIG_DIR = Path.home() / ".terminal-kitty"
CONFIG_FILE = CONFIG_DIR / "config.json"
PID_FILE = CONFIG_DIR / "terminal-kitty.pid"
ACTIVITY_FILE = CONFIG_DIR / "activity.json"


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
# 提醒输出（不干扰用户正常终端）
# ──────────────────────────────────────────────

def print_gentle(minutes):
    """第1档：轻量提醒，只输出一行"""
    print(CAT_GENTLE.format(minutes=minutes), flush=True)


def print_warning(minutes):
    """第2档：标准提醒，ASCII猫"""
    print(CAT_WARNING.format(minutes=minutes), flush=True)


def print_force(minutes):
    """第3档：强制占领，阻断终端"""
    print(CAT_FORCE.format(minutes=minutes), flush=True)


def print_cooldown():
    """休息确认后的反馈"""
    print(CAT_COOLDOWN, flush=True)


# ──────────────────────────────────────────────
# 强制模式：阻断终端输入
# ──────────────────────────────────────────────

def force_block():
    """
    阻断终端，等待用户按 Enter。
    使用 sys.stdin 读取，确保兼容性。
    """
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
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    thresholds = config["thresholds"]
    check_interval = config["check_interval"]
    cooldown_minutes = config["cooldown"]
    idle_timeout = config.get("idle_timeout", 120)

    # 状态
    elapsed_seconds = 0
    current_tier = 0  # 0=正常, 1=温柔, 2=警告, 3=强制
    in_cooldown = False
    cooldown_until = 0
    last_seen_activity = get_last_activity_time()

    print("🐱 Terminal Kitty 已启动，守护你的健康~", flush=True)
    print(f"   提醒阈值: {thresholds['gentle']}min / {thresholds['warning']}min / {thresholds['force']}min", flush=True)
    print(f"   检测间隔: {check_interval}s | 冷却时间: {cooldown_minutes}min | 空闲超时: {idle_timeout}s", flush=True)
    print("", flush=True)

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
                    print("🐱 冷却结束，猫咪重新开始守护~", flush=True)
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

            # 档位变化时触发提醒
            if new_tier > current_tier:
                current_tier = new_tier

                if current_tier == 1:
                    print_gentle(int(elapsed_minutes))
                elif current_tier == 2:
                    print_warning(int(elapsed_minutes))
                elif current_tier == 3:
                    print_force(int(elapsed_minutes))
                    force_block()
                    # 用户确认休息，进入冷却
                    print_cooldown()
                    in_cooldown = True
                    cooldown_until = time.time() + (cooldown_minutes * 60)

    except KeyboardInterrupt:
        pass
    finally:
        remove_pid()
        print("\n🐱 Terminal Kitty 已退出，下次见~", flush=True)


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
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    parser.add_argument("--stop", action="store_true", help="停止守护进程")
    parser.add_argument("--config", action="store_true", help="查看/编辑配置")
    parser.add_argument("--enabled", type=bool, help="启用/禁用")

    args = parser.parse_args()
    config = load_config()

    if args.ping:
        ping_activity()
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
