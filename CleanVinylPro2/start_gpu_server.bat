@echo off
chcp 65001 >nul
setlocal EnableExtensions

:: Якщо запущено вручну подвійним кліком (без --no-elevate / --direct) — запитуємо права Адміністратора
if /i "%~1"=="--no-elevate" goto :run_server
if /i "%~1"=="--direct" goto :run_server

net session >nul 2>&1
if errorlevel 1 (
    echo Запитуємо права Адміністратора для запуску GPU-сервера...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '--no-elevate' -Verb RunAs" >nul 2>&1
    if errorlevel 1 (
        echo [УВАГА] Не вдалося отримати права Адміністратора. Пробуємо звичайний запуск...
        goto :run_server
    )
    exit /b 0
)

:run_server
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

:: 1. Справжня HTTP-перевірка чи вже працює саме сервер Clean Vinyl Pro 2 v4.7.0 на порту 18746
"server\.venv\Scripts\python.exe" -c "import json, sys, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:18746/health', timeout=2); d=json.loads(r.read().decode('utf-8')); sys.exit(0 if d.get('ok') and d.get('app')=='cleanvinylpro2' and d.get('version')=='4.7.0' else 1)" >nul 2>&1
if not errorlevel 1 (
    echo [OK] AI GPU сервер Clean Vinyl Pro 2 v4.7.0 вже запущено на http://127.0.0.1:18746
    timeout /t 1 /nobreak >nul
    popd
    if /i "%~1"=="--no-elevate" exit 0
    if /i "%~1"=="--direct" exit 0
    exit /b 0
)

:: 2. Перевірка, чи процес python.exe САМЕ З ЦІЄЇ ПАПКИ вже зараз прогрівається після першого запуску
::    (стара програма Clean Vinyl Pro може працювати поруч - її процес сюди не рахується)
powershell -NoProfile -Command "$root = (Get-Location).Path.TrimEnd('\') + '\server\.venv\'; $p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'python*' -and $_.ExecutablePath -and $_.ExecutablePath.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) -and $_.CommandLine -like '*server.py*' }; if ($p) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo Сервер Clean Vinyl Pro 2 вже запускається, чекаємо готовності порту 18746...
    for /l %%i in (1,1,10) do (
        timeout /t 1 /nobreak >nul
        "server\.venv\Scripts\python.exe" -c "import json, sys, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:18746/health', timeout=2); d=json.loads(r.read().decode('utf-8')); sys.exit(0 if d.get('ok') and d.get('app')=='cleanvinylpro2' and d.get('version')=='4.7.0' else 1)" >nul 2>&1
        if not errorlevel 1 (
            echo [OK] AI GPU сервер Clean Vinyl Pro 2 v4.7.0 готовий!
            popd
            if /i "%~1"=="--no-elevate" exit 0
            if /i "%~1"=="--direct" exit 0
            exit /b 0
        )
    )
)

:: 3. Зупиняємо ТІЛЬКИ процес python, який сам слухає (LISTENING) порт 18746 (НІКОЛИ не чіпаємо Photoshop.exe!)
set "FOUND_OLD=0"
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /R /C:"127\.0\.0\.1:18746 .*LISTENING" /C:"0\.0\.0\.0:18746 .*LISTENING"') do (
    if not "%%p"=="0" (
        tasklist /FI "PID eq %%p" /NH 2>nul | findstr /I "python" >nul 2>&1
        if not errorlevel 1 (
            set "FOUND_OLD=1"
            taskkill /F /PID %%p >nul 2>nul
        )
    )
)
if "%FOUND_OLD%"=="1" (
    echo Зупинено попередню або завислу версію сервера на порту 18746...
    timeout /t 1 /nobreak >nul
)

echo Запуск AI GPU сервера Clean Vinyl Pro 2 v4.7.0...
echo (Ви можете згорнути це вікно, але не закривайте його під час роботи у Photoshop)
echo.
"server\.venv\Scripts\python.exe" "server\server.py"
if errorlevel 1 (
    echo.
    echo [ПОМИЛКА] Сервер завершився з помилкою. Перегляньте повідомлення вище.
)
pause
popd
