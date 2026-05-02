@echo off
REM Terminal Kitty 安装脚本 (Windows)

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set INSTALL_DIR=%USERPROFILE%\.terminal-kitty
set SETTINGS_FILE=%USERPROFILE%\.claude\settings.json

echo 🐱 Terminal Kitty 安装程序
echo ==========================
echo.

REM 1. 创建安装目录
echo 📁 创建安装目录: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM 2. 复制主程序
echo 📦 安装主程序...
copy /Y "%SCRIPT_DIR%terminal_kitty.py" "%INSTALL_DIR%\terminal_kitty.py" >nul

REM 3. 创建默认配置（如果不存在）
if not exist "%INSTALL_DIR%\config.json" (
    echo ⚙️  创建默认配置...
    (
        echo {
        echo   "enabled": true,
        echo   "thresholds": {
        echo     "gentle": 55,
        echo     "warning": 60,
        echo     "force": 70
        echo   },
        echo   "cooldown": 5,
        echo   "check_interval": 30
        echo }
    ) > "%INSTALL_DIR%\config.json"
) else (
    echo ⚙️  配置文件已存在，跳过
)

REM 4. 配置 Claude Code hook
if exist "%SETTINGS_FILE%" (
    echo 🔗 检测到 Claude Code，正在配置 hooks...
    python -c "
import json
sf=r'%SETTINGS_FILE%'
d=r'%INSTALL_DIR%'
with open(sf) as f: s=json.load(f)
h=s.setdefault('hooks',{})
def add(ev,data,key='terminal_kitty'):
    ls=h.setdefault(ev,[])
    if key not in str(ls): ls.append(data)
add('SessionStart',{'matcher':'startup','hooks':[{'type':'command','command':'python '+d+'\\terminal_kitty.py --daemon','async':True,'timeout':86400}]})
add('UserPromptSubmit',{'hooks':[{'type':'command','command':'python '+d+'\\terminal_kitty.py --ping'}]},'terminal_kitty_ping')
add('Stop',{'hooks':[{'type':'command','command':'python '+d+'\\terminal_kitty.py --check-reminder','timeout':15}]},'terminal_kitty_reminder')
add('SessionEnd',{'hooks':[{'type':'command','command':'taskkill /F /FI \"WINDOWTITLE eq terminal_kitty*\" 2>nul'}]})
with open(sf,'w') as f: json.dump(s,f,indent=2)
print('   ✅ Claude Code hooks 已配置')
" 2>nul || echo    ⚠️  配置 hooks 失败，请手动配置
) else (
    echo ℹ️  未检测到 Claude Code，跳过 hooks 配置
)

echo.
echo 🎉 安装完成！
echo.
echo 使用方法：
echo   python %INSTALL_DIR%\terminal_kitty.py          - 启动守护进程
echo   python %INSTALL_DIR%\terminal_kitty.py --status  - 查看状态
echo   python %INSTALL_DIR%\terminal_kitty.py --stop    - 停止守护进程
echo   python %INSTALL_DIR%\terminal_kitty.py --config  - 查看配置
echo.
echo 配置文件: %INSTALL_DIR%\config.json
echo.
echo 如需调整提醒时间，编辑 config.json 中的 thresholds 字段
echo.
echo 🐱 重启 Claude Code 后，Terminal Kitty将自动启动~

pause
