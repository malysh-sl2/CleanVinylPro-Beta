@echo off
chcp 65001 >nul
setlocal EnableExtensions

if /i not "%~1"=="--no-elevate" (
    net session >nul 2>&1
    if errorlevel 1 (
        echo Запитуємо права Адміністратора для перезапуску GPU-сервера...
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '--no-elevate' -Verb RunAs" >nul 2>&1
        if not errorlevel 1 exit /b 0
    )
)

pushd "%~dp0"

if not exist "server\.venv\Scripts\python.exe" (
    echo [ПОМИЛКА] Середовище ще не встановлено!
    echo Спочатку запустіть install_windows.bat від імені Адміністратора.
    pause
    popd
    exit /b 1
)

:: Python могли перенести або перевстановити: тоді середовище є, але не запускається
"server\.venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo [ПОМИЛКА] Середовище Python не запускається - схоже, Python перенесли або видалили.
    echo Запустіть install_windows.bat від імені Адміністратора: він полагодить це без повторного завантаження.
    pause
    popd
    exit /b 1
)

echo Зупиняємо попередній фоновий сервер Clean Vinyl Pro 2 (якщо працював)...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /R /C:"127\.0\.0\.1:18746 .*LISTENING" /C:"0\.0\.0\.0:18746 .*LISTENING"') do (
    if not "%%p"=="0" (
        tasklist /FI "PID eq %%p" /NH 2>nul | findstr /I "python" >nul 2>&1
        if not errorlevel 1 taskkill /F /PID %%p >nul 2>nul
    )
)
timeout /t 1 /nobreak >nul

echo Запускаємо оновлений AI GPU сервер Clean Vinyl Pro 2 v4.2.0...
echo (Ви можете згорнути це вікно, але не закривайте його під час роботи у Photoshop)
echo.
"server\.venv\Scripts\python.exe" "server\server.py"
if errorlevel 1 (
    echo.
    echo [ПОМИЛКА] Сервер завершився з помилкою. Перегляньте повідомлення вище.
)
pause
popd
