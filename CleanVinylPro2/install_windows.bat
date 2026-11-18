@echo off
chcp 65001 >nul
setlocal EnableExtensions

if /i not "%~1"=="--no-elevate" (
    net session >nul 2>&1
    if errorlevel 1 (
        echo Запитуємо права Адміністратора для встановлення Clean Vinyl Pro 2...
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '--no-elevate' -Verb RunAs" >nul 2>&1
        if not errorlevel 1 exit /b 0
    )
)

pushd "%~dp0"

echo ==============================================================
echo   Clean Vinyl Pro 2 v4.3.0 — Встановлення для Windows 11 + RTX 5060 Ti
echo ==============================================================
echo.

:: Зупиняємо старий сервер на порту 18746, якщо був відкритий (лише python, без сторонніх програм)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /R /C:"127\.0\.0\.1:18746 .*LISTENING" /C:"0\.0\.0\.0:18746 .*LISTENING"') do (
    if not "%%p"=="0" (
        tasklist /FI "PID eq %%p" /NH 2>nul | findstr /I "python" >nul 2>&1
        if not errorlevel 1 taskkill /F /PID %%p >nul 2>nul
    )
)

:: ---------------------------------------------------------------------------
:: 1. Шукаємо Python.
::    Спочатку папка з файлу folders.ini - рядок PYTHON_DIR, далі стандартні місця
::    встановлення, команда py, змінна PATH і спільна папка з рядка MODELS_DIR.
::    Кожен знайдений python.exe перевіряється запуском: 64-біт, версія 3.10 або новіша.
:: ---------------------------------------------------------------------------
set "CVP_PY="
set "CVP_PYDIR="
set "CVP_SHARED="
if exist "folders.ini" for /f "tokens=1,* delims==" %%a in ('findstr /b /i /c:"PYTHON_DIR=" "folders.ini" 2^>nul') do set "CVP_PYDIR=%%~b"
if exist "folders.ini" for /f "tokens=1,* delims==" %%a in ('findstr /b /i /c:"MODELS_DIR=" "folders.ini" 2^>nul') do set "CVP_SHARED=%%~b"

if defined CVP_PYDIR call :try_python "%CVP_PYDIR%\python.exe"
for %%v in (312 313 311 310 314) do call :try_python "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
for %%v in (312 313 311 310 314) do call :try_python "%ProgramFiles%\Python%%v\python.exe"
for %%v in (312 313 311 310 314) do call :try_python "C:\Python%%v\python.exe"
if not defined CVP_PY for /f "delims=" %%p in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do call :try_python "%%p"
if not defined CVP_PY for /f "delims=" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do call :try_python "%%p"
if not defined CVP_PY for /f "delims=" %%p in ('where python 2^>nul') do call :try_python "%%p"
call :try_python "C:\python.exe"
if not defined CVP_PY if defined CVP_SHARED call :try_python "%CVP_SHARED%\python.exe"
if not defined CVP_PY if defined CVP_SHARED for /d %%d in ("%CVP_SHARED%\*") do call :try_python "%%~d\python.exe"
if not defined CVP_PY goto :no_python

echo Python: "%CVP_PY%"
echo.

:: ---------------------------------------------------------------------------
:: 2. Усе інше робить server\setup_env.py:
::    бібліотеки Python - спільна папка LIBS_DIR, нічого не завантажується вдруге;
::    AI-моделі - спільна папка MODELS_DIR; перевірка відеокарти; запуск із Photoshop.
:: ---------------------------------------------------------------------------
"%CVP_PY%" "server\setup_env.py" install
if errorlevel 1 goto :setup_failed

:: ---------------------------------------------------------------------------
:: 3. Встановлення плагіна .ccx у Photoshop через Adobe UPIA
:: ---------------------------------------------------------------------------
echo.
echo ==============================================================
echo   Встановлення плагіна у Photoshop
echo ==============================================================
set "UPIA=C:\Program Files\Common Files\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe"
if not exist "%UPIA%" goto :no_upia
echo Знайдено Adobe Plugin Installer. Встановлюємо CleanVinylPro2.ccx...
"%UPIA%" /install "%~dp0CleanVinylPro2.ccx"
goto :finish

:no_upia
echo Автоматичний інсталятор Adobe не знайдено за стандартним шляхом.
echo Двічі клацніть файл CleanVinylPro2.ccx у цій папці і підтвердьте встановлення.

:finish
echo.
echo ==============================================================
echo   ГОТОВО!
echo   • Автозапуск разом із ПК ВИМКНЕНО.
echo   • GPU-сервер запускається через start_gpu_server.bat або з кнопки в Photoshop.
echo ==============================================================
pause
popd
exit /b 0

:setup_failed
echo.
echo ==============================================================
echo   ВСТАНОВЛЕННЯ НЕ ЗАВЕРШЕНО - прочитайте повідомлення вище.
echo   Усе, що тут було написано, збережено у файлі server\install.log
echo ==============================================================
pause
popd
exit /b 1

:no_python
echo.
echo [ПОМИЛКА] Не знайдено 64-бітний Python версії 3.10 або новішої.
echo.
echo Де шукали:
echo   1. Папка з файлу folders.ini, рядок PYTHON_DIR: "%CVP_PYDIR%"
echo   2. "%LOCALAPPDATA%\Programs\Python"
echo   3. Стандартні папки, команда py, змінна PATH, спільна папка з рядка MODELS_DIR.
echo.
echo Що зробити:
echo   - якщо Python встановлено в іншому місці: відкрийте Блокнотом файл folders.ini
echo     у цій папці, у рядку PYTHON_DIR= впишіть папку, де лежить python.exe,
echo     збережіть файл і запустіть install_windows.bat ще раз;
echo   - якщо Python не встановлено: https://www.python.org/downloads/  - версія 3.12.
pause
popd
exit /b 1

:: ---------------------------------------------------------------------------
:: Підпрограма: якщо Python ще не вибрано, а переданий файл існує і справді
:: запускається як 64-бітний Python 3.10 або новіший - запам'ятовує його у CVP_PY.
:: ---------------------------------------------------------------------------
:try_python
if defined CVP_PY goto :eof
if not exist "%~1" goto :eof
"%~1" -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) and sys.maxsize > 2**32 else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set "CVP_PY=%~1"
goto :eof
