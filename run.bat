@echo off
title AMEVA-Crawler
cd /d "%~dp0"
echo ===================================================
echo   Starting AMEVA-Crawler with System Tray...
echo ===================================================
where pyw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pyw app.py
) else (
    where py >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        py -3 app.py
    ) else (
        python app.py
    )
)
