"""
AMEVA-Crawler Main Application Entrypoint
Zero-dependency, pure Python intelligent web crawler with SQLite3, Telegram notification, and Tkinter GUI.
"""
import sys
import os
import tkinter as tk

# Ensure current dir is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
from scheduler import scheduler_instance
from gui import AMEVACrawlerGUI

def main():
    # 1. Initialize SQLite Database
    db.init_db()

    # 2. Start Background Scheduler Engine
    scheduler_instance.start()

    # 3. Create Tkinter GUI
    root = tk.Tk()
    app = AMEVACrawlerGUI(root)

    # Handle window close
    def on_closing():
        try:
            scheduler_instance.stop()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 4. Start GUI Event Loop
    try:
        root.mainloop()
    except KeyboardInterrupt:
        on_closing()

if __name__ == "__main__":
    main()
