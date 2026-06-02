@echo off
chcp 65001 >nul
title Cuanmology Bot

echo ============================================================
echo   CUANMOLOGY BOT — Background Scanner (Telegram Alerts)
echo   Tekan Ctrl+C untuk menghentikan
echo ============================================================
echo.

if not exist venv (
    echo [ERROR] Jalankan run.bat terlebih dahulu untuk setup environment.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python bot.py

pause
