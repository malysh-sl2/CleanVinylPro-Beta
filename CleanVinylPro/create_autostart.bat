@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "server\.venv\Scripts\python.exe" (
    echo [ПОМИЛКА] Спочатку запустіть install_windows.bat!
    pause
    exit /b 1
)

"server\.venv\Scripts\python.exe" "server\setup_launcher.py"
pause
