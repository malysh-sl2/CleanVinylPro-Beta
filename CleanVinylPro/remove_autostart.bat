@echo off
chcp 65001 >nul
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CleanVinylProServer.vbs"
if exist "%STARTUP%" (
    del "%STARTUP%"
    echo [OK] Автозапуск при старті Windows видалено.
) else (
    echo Автозапуск Windows уже вимкнено.
)
schtasks /Delete /TN "CleanVinylProServer" /F >nul 2>nul
reg delete "HKCU\Software\Classes\cleanvinyl" /f >nul 2>nul
echo Протокол cleanvinyl:// та завдання CleanVinylProServer очищено.
pause
