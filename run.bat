@echo off
chcp 65001 > nul
title AMEVA-Crawler
cd /d "%~dp0"

echo ===================================================
echo   Starting AMEVA-Crawler (Autonomous Web Monitor)
echo ===================================================

if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" app.py
    goto :done
)

where pyw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pyw app.py
    goto :done
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" py -3 app.py
    goto :done
)

python app.py

:done
