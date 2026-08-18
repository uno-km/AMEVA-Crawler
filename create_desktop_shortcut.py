"""
Script to create Desktop shortcut and launcher with custom AMEVA Brand Icon.
"""
import os
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PY = os.path.join(BASE_DIR, "app.py")
ICON_ICO = os.path.join(BASE_DIR, "assets", "icon.ico")
DESKTOP_DIR = os.path.join(os.environ["USERPROFILE"], "Desktop")

# 1. Find pythonw / pyw or python for silent background start
pythonw_path = ""
for candidate in [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Launcher", "pyw.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312", "pythonw.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python311", "pythonw.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python310", "pythonw.exe"),
    "pythonw.exe",
    "pyw.exe",
    "py.exe"
]:
    if os.path.exists(candidate):
        pythonw_path = candidate
        break

if not pythonw_path:
    pythonw_path = "pyw.exe"

# 2. Create Windows Shortcut (.lnk) via PowerShell WScript.Shell
shortcut_path = os.path.join(DESKTOP_DIR, "AMEVA-Crawler.lnk")
ps_script = f"""
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{pythonw_path}"
$Shortcut.Arguments = '"{APP_PY}"'
$Shortcut.WorkingDirectory = "{BASE_DIR}"
$Shortcut.IconLocation = "{ICON_ICO}, 0"
$Shortcut.Description = "AMEVA-Crawler (Autonomous Web Monitor)"
$Shortcut.Save()
"""

try:
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
    print(f"[+] Created Desktop Shortcut: {shortcut_path}")
except Exception as e:
    print(f"[-] Failed to create shortcut via PowerShell: {e}")

# 3. Also create Desktop AMEVA-Crawler.bat for convenience
desktop_bat_path = os.path.join(DESKTOP_DIR, "AMEVA-Crawler.bat")
bat_content = f"""@echo off
cd /d "{BASE_DIR}"
where pyw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pyw app.py
) else (
    where py >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        start "" py -3 app.py
    ) else (
        start "" python app.py
    )
)
"""
with open(desktop_bat_path, "w", encoding="utf-8") as f:
    f.write(bat_content)

print(f"[+] Created Desktop Launcher Bat: {desktop_bat_path}")
