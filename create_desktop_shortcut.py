"""
Script to create Desktop shortcut with official AMEVA Brand Icon.
"""
import os
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PY = os.path.join(BASE_DIR, "app.py")
ICON_ICO = os.path.join(BASE_DIR, "assets", "icon.ico")
DESKTOP_DIR = os.path.join(os.environ["USERPROFILE"], "Desktop")

# 1. Prioritize Python 3.12 pythonw.exe or pyw.exe for silent background start
pythonw_path = ""
for candidate in [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312", "pythonw.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Launcher", "pyw.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python311", "pythonw.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python310", "pythonw.exe"),
    "pythonw.exe",
    "pyw.exe",
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
$Shortcut.Description = "AMEVA-Crawler (실시간 웹 변경 모니터링)"
$Shortcut.Save()
"""

try:
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
    print(f"[+] Created Desktop Shortcut: {shortcut_path}")
except Exception as e:
    print(f"[-] Failed to create shortcut via PowerShell: {e}")

# 3. Clean up unwanted redundant .bat file from Desktop if present
desktop_bat_path = os.path.join(DESKTOP_DIR, "AMEVA-Crawler.bat")
if os.path.exists(desktop_bat_path):
    try:
        os.remove(desktop_bat_path)
        print(f"[+] Removed redundant Desktop bat: {desktop_bat_path}")
    except Exception as e:
        print(f"[-] Could not remove {desktop_bat_path}: {e}")
