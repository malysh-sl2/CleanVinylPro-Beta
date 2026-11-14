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

echo [0/4] Зупиняємо старий фоновий сервер на порту 18745 (якщо запущено)...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":18745 "') do (
    if not "%%p"=="0" taskkill /F /PID %%p >nul 2>nul
)

call "server\.venv\Scripts\activate.bat"

echo [1/4] Шукаємо nvidia-smi та перевіряємо версію CUDA драйвера...
python -c "import subprocess, re, sys, shutil, os; smi=shutil.which('nvidia-smi') or (r'C:\Windows\System32\nvidia-smi.exe' if os.path.exists(r'C:\Windows\System32\nvidia-smi.exe') else (r'C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe' if os.path.exists(r'C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe') else None)); out=subprocess.check_output([smi], stderr=subprocess.DEVNULL).decode('utf-8','ignore') if smi else ''; print(out.splitlines()[1] if len(out.splitlines())>1 else 'nvidia-smi not found'); m=re.search(r'CUDA Version:\s*(\d+)\.(\d+)', out); maj,min_= (int(m.group(1)),int(m.group(2))) if m else (0,0); print(f'Підтримувана драйвером CUDA: {maj}.{min_}'); sys.exit(13 if maj>=13 else (12 if maj==12 else 1))"
set CUDA_CODE=%errorlevel%

echo.
echo [2/4] Перевстановлюємо onnxruntime-gpu (CUDA)...
pip uninstall -y onnxruntime onnxruntime-gpu onnxruntime-directml >nul 2>nul

if "%CUDA_CODE%"=="13" (
    echo Встановлюємо onnxruntime-gpu[cuda,cudnn] для CUDA 13...
    pip install --no-cache-dir --upgrade "onnxruntime-gpu[cuda,cudnn]>=1.27.0"
) else if "%CUDA_CODE%"=="12" (
    echo Встановлюємо onnxruntime-gpu==1.26.0[cuda,cudnn] для CUDA 12...
    pip install --no-cache-dir "onnxruntime-gpu[cuda,cudnn]==1.26.0"
) else (
    echo Встановлюємо onnxruntime-gpu[cuda,cudnn]...
    pip install --no-cache-dir --upgrade "onnxruntime-gpu[cuda,cudnn]>=1.27.0"
)

if errorlevel 1 (
    echo [УВАГА] Повний пакет із cuda,cudnn не встановився, пробуємо базовий onnxruntime-gpu...
    pip install --no-cache-dir onnxruntime-gpu
)

python -c "import onnxruntime as ort; print('Встановлено onnxruntime:', ort.__version__, ort.get_available_providers())"
if errorlevel 1 (
    echo [УВАГА] Ставимо запасний CPU onnxruntime, щоб сервер точно запускався...
    pip install --no-cache-dir onnxruntime
)

echo.
echo [3/4] Перевіряємо AI-модель LaMa FP32 (чистий FP32 без DequantizeLinear для GPU)...
python "server\download_models.py"

echo.
echo [4/4] Тестуємо реальний прогін обох моделей на вашій RTX 5060 Ti...
python -c "import sys, numpy as np; sys.path.insert(0, 'server'); import engine, onnxruntime as ort; print('DLL dirs registered:', len(engine._NVIDIA_DLL_DIRS)); print('Available providers:', ort.get_available_providers()); eng = engine.CleanVinylEngine('server/models'); print('Active Provider:', eng.provider_name); print('Active GPU:', eng.gpu_name); test_rgba = np.zeros((512, 512, 4), dtype=np.uint8); test_sel = np.zeros((512, 512), dtype=np.uint8); test_sel[100:140, 100:140] = 255; out, st = eng.process(test_rgba, 8, {'spots':75,'scuffs':65,'seamOn':False,'seam':0,'edge':70,'smokeOn':False,'smoke':0,'grain':90,'shadow':True,'removeStands':False,'master':100}, test_sel); print('REAL GPU TEST OK:', st); print('GPU Error (if any):', eng.gpu_error or 'None')"

echo.
pause
