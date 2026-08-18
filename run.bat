@echo off
title AMEVA-Crawler
cd /d "%~dp0"
echo ===================================================
echo   Starting AMEVA-Crawler (Python Tkinter GUI)...
echo ===================================================
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -3 app.py
) else (
    python app.py
)
