#!/usr/bin/env bash
# Terminal Kitty 安装脚本 (Mac/Linux)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.terminal-kitty"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo "🐱 Terminal Kitty 安装程序"
echo "=========================="
echo ""

# 1. 创建安装目录
echo "📁 创建安装目录: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# 2. 复制主程序
echo "📦 安装主程序..."
cp "$SCRIPT_DIR/terminal_kitty.py" "$INSTALL_DIR/terminal_kitty.py"
chmod +x "$INSTALL_DIR/terminal_kitty.py"

# 3. 创建默认配置（如果不存在）
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    echo "⚙️  创建默认配置..."
    cat > "$INSTALL_DIR/config.json" << 'EOF'
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
EOF
else
    echo "⚙️  配置文件已存在，跳过"
fi

# 4. 配置 Claude Code hook（如果存在 settings.json）
if [ -f "$SETTINGS_FILE" ]; then
    echo "🔗 检测到 Claude Code，正在配置 hooks..."

    # 使用 Python 安全地修改 JSON
    python3 -c "
import json

settings_file = '$SETTINGS_FILE'
install_dir = '$INSTALL_DIR'

with open(settings_file, 'r') as f:
    settings = json.load(f)

if 'hooks' not in settings:
    settings['hooks'] = {}

def add_hook(event, hook_data, check_key='terminal_kitty'):
    if event not in settings['hooks']:
        settings['hooks'][event] = []
    existing = [h for h in settings['hooks'][event] if check_key in str(h)]
    if not existing:
        settings['hooks'][event].append(hook_data)

# SessionStart: 启动守护进程
add_hook('SessionStart', {
    'matcher': 'startup',
    'hooks': [{
        'type': 'command',
        'command': f'python3 {install_dir}/terminal_kitty.py --daemon &',
        'async': True,
        'timeout': 86400
    }]
})

# UserPromptSubmit: 用户输入时记录活动
add_hook('UserPromptSubmit', {
    'hooks': [{
        'type': 'command',
        'command': f'python3 {install_dir}/terminal_kitty.py --ping'
    }]
}, 'terminal_kitty_ping')

# Stop: Claude 回复结束时显示提醒
add_hook('Stop', {
    'hooks': [{
        'type': 'command',
        'command': f'python3 {install_dir}/terminal_kitty.py --check-reminder',
        'timeout': 15
    }]
}, 'terminal_kitty_reminder')

# SessionEnd: 停止守护进程
add_hook('SessionEnd', {
    'hooks': [{
        'type': 'command',
        'command': \"pkill -f 'terminal_kitty.py --daemon' 2>/dev/null || true\"
    }]
})

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

print('   ✅ Claude Code hooks 已配置（SessionStart/UserPromptSubmit/Stop/SessionEnd）')
" 2>/dev/null || echo "   ⚠️  配置 hooks 失败，请手动配置"
else
    echo "ℹ️  未检测到 Claude Code，跳过 hooks 配置"
fi

# 5. 添加到 PATH（可选）
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "terminal-kitty" "$SHELL_RC" 2>/dev/null; then
        echo ""
        read -p "是否添加 terminal-kitty 到 PATH？(y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$SHELL_RC"
            echo "✅ 已添加到 $SHELL_RC，请运行 source $SHELL_RC 生效"
        fi
    fi
fi

echo ""
echo "🎉 安装完成！"
echo ""
echo "使用方法："
echo "  python3 $INSTALL_DIR/terminal_kitty.py          # 启动守护进程"
echo "  python3 $INSTALL_DIR/terminal_kitty.py --status  # 查看状态"
echo "  python3 $INSTALL_DIR/terminal_kitty.py --stop    # 停止守护进程"
echo "  python3 $INSTALL_DIR/terminal_kitty.py --config  # 查看配置"
echo ""
echo "配置文件: $INSTALL_DIR/config.json"
echo ""
echo "如需调整提醒时间，编辑 config.json 中的 thresholds 字段"
echo ""
echo "🐱 重启 Claude Code 后，Terminal Kitty将自动启动~"
