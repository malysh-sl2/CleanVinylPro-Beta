@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo ==============================================================
echo   Clean Vinyl Pro — Діагностика та ремонт NVIDIA GPU (CUDA)
echo ==============================================================
echo.

if not exist "server\.venv\Scripts\python.exe" (
    echo [ПОМИЛКА] Папку server\.venv ще не створено. Спочатку запустіть install_windows.bat!
    pause
    exit /b 1
)

echo [0/4] Зупиняємо фоновий сервер Clean Vinyl Pro на порту 18746 (якщо запущено)...
:: лише процес python, який сам слухає цей порт (жодних сторонніх програм і не стару Clean Vinyl Pro на 18745)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /R /C:"127\.0\.0\.1:18746 .*LISTENING" /C:"0\.0\.0\.0:18746 .*LISTENING"') do (
    if not "%%p"=="0" (
        tasklist /FI "PID eq %%p" /NH 2>nul | findstr /I "python" >nul 2>&1
        if not errorlevel 1 taskkill /F /PID %%p >nul 2>nul
    )
)

:: Усе робить server\setup_env.py: версія CUDA драйвера, перевстановлення onnxruntime-gpu там,
:: де лежать бібліотеки (спільна папка LIBS_DIR або server\.venv), моделі, реальний прогін на відеокарті.
"server\.venv\Scripts\python.exe" "server\setup_env.py" gpu
if errorlevel 1 (
    echo.
    echo [УВАГА] Ремонт не завершено - прочитайте повідомлення вище.
    echo Якщо написано, що середовище не запускається, - запустіть install_windows.bat від імені Адміністратора.
)

echo.
pause
