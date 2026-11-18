@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "server\.venv\Scripts\python.exe" (
    echo [ПОМИЛКА] Спочатку запустіть install_windows.bat!
    pause
    exit /b 1
)

echo Налаштування:
echo  1) Автоматичний запуск сервера разом із Windows (тихо у фоні)
echo  2) Запуск GPU-сервера прямо з кнопки всередині Photoshop (cleanvinyl2://)
echo.
"server\.venv\Scripts\python.exe" "server\setup_launcher.py"
echo.
echo Готово! Тепер ви можете запускати GPU-сервер прямо з панелі Photoshop!
pause
