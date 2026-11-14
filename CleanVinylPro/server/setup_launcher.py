import ctypes
import os
import subprocess
import sys
from xml.sax.saxutils import escape as _xml_esc


def _is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _save_install_path(root_dir: str):
    try:
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
            data_dir = os.path.join(appdata, "CleanVinylPro")
        else:
            data_dir = os.path.join(os.path.expanduser("~"), ".cleanvinylpro")
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "install_path.txt"), "w", encoding="utf-8") as f:
            f.write(root_dir)
    except Exception:
        pass


def _register_elevated_task(root_dir: str, start_bat: str) -> bool:
    """
    Creates an on-demand Windows Scheduled Task ('CleanVinylProServer') with Highest Privileges (Admin)
    and zero triggers, so Photoshop's launch button can start the server elevated with ZERO UAC popups.
    """
    if sys.platform != "win32" or not _is_admin():
        return False
    try:
        user_id = os.environ.get("USERDOMAIN", "")
        user_name = os.environ.get("USERNAME", "")
        principal_id = f"{user_id}\\{user_name}" if user_id and user_name else user_name

        # Build minimal Task Scheduler XML with no triggers (runs ONLY on explicit schtasks /Run)
        xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Principals>
    <Principal id="Author">
      <UserId>{_xml_esc(principal_id)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>5</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c start "Clean Vinyl Pro GPU Server" /min cmd.exe /c ""{_xml_esc(start_bat)}" --no-elevate"</Arguments>
      <WorkingDirectory>{_xml_esc(root_dir)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
        xml_tmp = os.path.join(root_dir, "server", "_task_tmp.xml")
        with open(xml_tmp, "w", encoding="utf-16") as f:
            f.write(xml_content)
        try:
            res = subprocess.run(
                ["schtasks", "/Create", "/TN", "CleanVinylProServer", "/XML", xml_tmp, "/F"],
                capture_output=True,
                text=True,
            )
            return res.returncode == 0
        finally:
            try:
                os.remove(xml_tmp)
            except Exception:
                pass
    except Exception:
        return False


def main():
    server_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(server_dir)
    start_bat = os.path.join(root_dir, "start_gpu_server.bat")
    vbs_path = os.path.join(server_dir, "launch_server_minimized.vbs")

    _save_install_path(root_dir)
    task_ok = _register_elevated_task(root_dir, start_bat)

    def esc_vbs(s: str) -> str:
        return s.replace('"', '""')

    # First tries elevated Scheduled Task (zero UAC popup + Admin rights);
    # falls back cleanly to minimized direct launch if task wasn't registered.
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.CurrentDirectory = "{esc_vbs(root_dir)}"\r\n'
        'rc = 1\r\n'
        'On Error Resume Next\r\n'
        'rc = WshShell.Run("schtasks /Run /TN ""CleanVinylProServer""", 0, True)\r\n'
        'On Error GoTo 0\r\n'
        'If rc <> 0 Then\r\n'
        f'    WshShell.Run "cmd.exe /c """"{esc_vbs(start_bat)}"" --direct""", 7, False\r\n'
        'End If\r\n'
    )

    with open(vbs_path, "w", encoding="utf-16") as f:
        f.write(vbs_content)

    old_vbs = os.path.join(server_dir, "launch_server_hidden.vbs")
    if os.path.exists(old_vbs):
        try:
            os.remove(old_vbs)
        except Exception:
            pass

    if sys.platform == "win32":
        import winreg

        appdata = os.environ.get("APPDATA", "")
        if appdata:
            startup_vbs = os.path.join(
                appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "CleanVinylProServer.vbs"
            )
            if os.path.exists(startup_vbs):
                try:
                    os.remove(startup_vbs)
                    print("[OK] Видалено старий автозапуск із Windows Startup")
                except Exception:
                    pass

        cmd = f'wscript.exe "{vbs_path}"'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\cleanvinyl") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:Clean Vinyl Pro GPU Server")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\cleanvinyl\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
        print("[OK] Зареєстровано запуск GPU-сервера прямо з Photoshop (cleanvinyl://)")
        if task_ok:
            print("[OK] Зареєстровано запуск із правами Адміністратора без вікна UAC (CleanVinylProServer)")
        else:
            print("[INFO] Щоб запуск із Photoshop також мав права Адміністратора без UAC, запустіть setup_ps_launch.bat від адміністратора.")
    else:
        print("Non-Windows platform detected; created minimized VBS:", vbs_path)


if __name__ == "__main__":
    main()
