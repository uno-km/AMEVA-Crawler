"""
AMEVA-Crawler Main Application Entrypoint
Zero-dependency, pure Python intelligent web crawler with SQLite3, Telegram notification,
Tkinter GUI, and Windows System Tray integration.
"""
import sys
import os
import tkinter as tk

# Ensure current dir is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
from scheduler import scheduler_instance
from gui import AMEVACrawlerGUI, ICON_PATH
import tray

def main():
    # 1. Initialize SQLite Database
    db.init_db()

    # 2. Start Background Scheduler Engine
    scheduler_instance.start()

    # 3. Create Tkinter GUI
    root = tk.Tk()

    # Callbacks for Tray
    def on_tray_show():
        root.after(0, app.show_window)

    def on_tray_run_all():
        active_targets = db.get_active_targets()
        for t in active_targets:
            scheduler_instance.trigger_immediate(t["id"])
        if tray_icon:
            tray_icon.show_balloon("AMEVA-Crawler", f"활성 타겟 {len(active_targets)}개 크롤링을 요청했습니다.")

    def on_tray_exit():
        def _cleanup_and_destroy():
            try:
                scheduler_instance.stop()
            except Exception:
                pass
            try:
                if tray_icon:
                    tray_icon.stop()
            except Exception:
                pass
            root.destroy()
            os._exit(0)

        root.after(0, _cleanup_and_destroy)

    # 4. Initialize Windows System Tray Icon
    tray_icon = tray.WindowsTrayIcon(
        icon_path=ICON_PATH,
        tooltip="AMEVA-Crawler (실시간 웹 변경 모니터링)",
        on_show=on_tray_show,
        on_run_all=on_tray_run_all,
        on_exit=on_tray_exit
    )
    tray.global_tray_instance = tray_icon
    tray_icon.start()

    # 5. Initialize GUI with Tray Reference
    app = AMEVACrawlerGUI(root, tray=tray_icon)

    # Handle window 'X' close button -> Minimize to System Tray
    root.protocol("WM_DELETE_WINDOW", app.minimize_to_tray)

    # 6. Start GUI Event Loop
    try:
        root.mainloop()
    except KeyboardInterrupt:
        on_tray_exit()

if __name__ == "__main__":
    main()
