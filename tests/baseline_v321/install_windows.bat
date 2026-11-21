@echo off
chcp 65001 >nul
setlocal EnableExtensions

if /i not "%~1"=="--no-elevate" (
    net session >nul 2>&1
    if errorlevel 1 (
        echo Запитуємо права Адміністратора для встановлення Clean Vinyl Pro...
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '--no-elevate' -Verb RunAs" >nul 2>&1
        if not errorlevel 1 exit /b 0
    )
)

pushd "%~dp0"

echo ==============================================================
echo   Clean Vinyl Pro — Встановлення для Windows 11 + RTX 5060 Ti
echo ==============================================================
echo.

:: Зупиняємо старий сервер на порту 18745, якщо був відкритий (лише python, без сторонніх програм)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /R /C:"127\.0\.0\.1:18745 .*LISTENING" /C:"0\.0\.0\.0:18745 .*LISTENING"') do (
    if not "%%p"=="0" (
        tasklist /FI "PID eq %%p" /NH 2>nul | findstr /I "python" >nul 2>&1
        if not errorlevel 1 taskkill /F /PID %%p >nul 2>nul
    )
)

:: 1. Перевірка Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ПОМИЛКА] Python не знайдено у системі.
    echo Встановіть Python 3.11 або 3.12 з https://www.python.org/downloads/
    echo ВАЖЛИВО: поставте галочку "Add python.exe to PATH".
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version') do echo Знайдено %%v

:: 2. Створення віртуального середовища
if not exist "server\.venv\Scripts\python.exe" (
    echo.
    echo [1/5] Створюємо ізольоване середовище Python...
    python -m venv "server\.venv"
    if errorlevel 1 (
        echo [ПОМИЛКА] Не вдалося створити .venv
        pause
        exit /b 1
    )
)

call "server\.venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul

:: 3. Встановлення базових бібліотек
echo.
echo [2/5] Встановлюємо бібліотеки сервера та OpenCV...
pip install -r "server\requirements.txt"
if errorlevel 1 (
    echo [ПОМИЛКА] Помилка встановлення пакетів з requirements.txt
    pause
    exit /b 1
)

:: 4. Визначення версії CUDA драйвера NVIDIA (включно зі стандартними шляхами Windows)
echo.
echo [3/5] Налаштування GPU-прискорення під NVIDIA RTX 5060 Ti...
python -c "import subprocess, re, sys, shutil, os; smi=shutil.which('nvidia-smi') or (r'C:\Windows\System32\nvidia-smi.exe' if os.path.exists(r'C:\Windows\System32\nvidia-smi.exe') else (r'C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe' if os.path.exists(r'C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe') else None)); out=subprocess.check_output([smi], stderr=subprocess.DEVNULL).decode('utf-8','ignore') if smi else ''; m=re.search(r'CUDA Version:\s*(\d+)\.(\d+)', out); maj,min_= (int(m.group(1)),int(m.group(2))) if m else (0,0); print(f'NVIDIA Driver CUDA: {maj}.{min_}' if smi else 'nvidia-smi not found'); sys.exit(13 if maj>=13 else (12 if maj==12 else 1))"
set CUDA_CODE=%errorlevel%

pip uninstall -y onnxruntime onnxruntime-gpu onnxruntime-directml >nul 2>nul

if "%CUDA_CODE%"=="13" (
    echo Виявлено драйвер CUDA 13+. Встановлюємо onnxruntime-gpu[cuda,cudnn]...
    pip install --no-cache-dir --upgrade "onnxruntime-gpu[cuda,cudnn]>=1.27.0"
) else if "%CUDA_CODE%"=="12" (
    echo Виявлено драйвер CUDA 12.x. Встановлюємо onnxruntime-gpu==1.26.0 + CUDA 12 бібліотеки...
    pip install --no-cache-dir "onnxruntime-gpu[cuda,cudnn]==1.26.0"
) else (
    echo [УВАГА] Драйвер NVIDIA не знайдено! Ставимо onnxruntime-gpu...
    pip install --no-cache-dir "onnxruntime-gpu[cuda,cudnn]>=1.27.0"
)

if errorlevel 1 (
    echo Пробуємо резервне встановлення onnxruntime-gpu...
    pip install --no-cache-dir onnxruntime-gpu
)

python -c "import onnxruntime" >nul 2>nul
if errorlevel 1 (
    echo Встановлюємо резервний onnxruntime...
    pip install --no-cache-dir onnxruntime
)

:: 5. Завантаження AI-моделей
echo.
echo [4/5] Завантаження AI-моделей (bria-rmbg-2.0 та LaMa)...
python "server\download_models.py"
if errorlevel 1 (
    echo [ПОМИЛКА] Не вдалося завантажити AI-моделі. Перевірте інтернет-з'єднання.
    pause
    exit /b 1
)

:: 6. Реальна перевірка GPU
echo.
echo Перевіряємо реальний запуск моделей на GPU...
python -c "import sys; sys.path.insert(0,'server'); import engine; eng=engine.CleanVinylEngine('server/models'); print('Active Device:', eng.gpu_name); print('Active Provider:', eng.provider_name); print('GPU Warning:', eng.gpu_error or 'None')"

:: 7. Реєстрація запуску кнопкою з Photoshop (cleanvinyl://) БЕЗ автозапуску з ПК
echo.
echo [5/5] Реєстрація запуску GPU-сервера прямо з Photoshop (без автозапуску ПК)...
python "server\setup_launcher.py"

:: 8. Спроба автоматично встановити .ccx у Photoshop 2026 через Adobe UPIA
echo.
echo ==============================================================
echo   Встановлення плагіна у Photoshop 2026
echo ==============================================================
set "UPIA=C:\Program Files\Common Files\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe"
if exist "%UPIA%" (
    echo Знайдено Adobe Plugin Installer. Встановлюємо CleanVinylPro.ccx...
    "%UPIA%" /install "%~dp0CleanVinylPro.ccx"
) else (
    echo Автоматичний інсталятор Adobe не знайдено за стандартним шляхом.
    echo Ви можете:
    echo   1) Двічі клацнути по файлу CleanVinylPro.ccx у цій папці, АБО
    echo   2) Відкрити Adobe UXP Developer Tool ^-> Add Plugin ^-> обрати uxp-plugin\manifest.json ^-> Load.
)

echo.
echo ==============================================================
echo   ГОТОВО!
echo   • Автозапуск разом із ПК ВИМКНЕНО.
echo   • GPU-сервер запускається через start_gpu_server.bat або з кнопки в Photoshop.
echo ==============================================================
pause
