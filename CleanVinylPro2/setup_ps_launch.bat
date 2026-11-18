@echo off
chcp 65001 >nul
setlocal EnableExtensions

if /i not "%~1"=="--no-elevate" (
    net session >nul 2>&1
    if errorlevel 1 (
        echo Запитуємо права Адміністратора для налаштування запуску з Photoshop...
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '--no-elevate' -Verb RunAs" >nul 2>&1
        if not errorlevel 1 exit /b 0
    )
)

pushd "%~dp0"

if not exist "server\.venv\Scripts\python.exe" (
    echo [ПОМИЛКА] Спочатку запустіть install_windows.bat від імені Адміністратора!
    pause
    popd
    exit /b 1
)

echo Налаштування запуску GPU-сервера з Photoshop (з правами Адміністратора без зайвих запитів UAC)...
"server\.venv\Scripts\python.exe" "server\setup_launcher.py"
echo.
echo Перевірка GPU у вашому середовищі:
"server\.venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'server'); import engine, onnxruntime as ort; print('ONNX Providers:', ort.get_available_providers()); print('NVIDIA DLL dirs:', len(engine._NVIDIA_DLL_DIRS))"
echo.
echo Готово! Автозапуск із Windows вимкнено, а запуск із Photoshop налаштовано.
pause
popd
