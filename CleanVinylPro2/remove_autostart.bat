@echo off
chcp 65001 >nul
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CleanVinylPro2Server.vbs"
if exist "%STARTUP%" (
    del "%STARTUP%"
    echo [OK] Автозапуск при старті Windows видалено.
) else (
    echo Автозапуск Windows уже вимкнено.
)
schtasks /Delete /TN "CleanVinylPro2Server" /F >nul 2>nul
reg delete "HKCU\Software\Classes\cleanvinyl2" /f >nul 2>nul
echo Протокол cleanvinyl2:// та завдання CleanVinylPro2Server очищено.
pause
