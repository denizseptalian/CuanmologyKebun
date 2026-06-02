@echo off
chcp 65001 >nul
title Cuanmology

echo ============================================================
echo   CUANMOLOGY — Setup dan Jalankan
echo ============================================================
echo.

:: Cek Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan. Install Python 3.10+ dari python.org
    pause
    exit /b 1
)

:: Buat .env jika belum ada
if not exist .env (
    echo [INFO] File .env belum ada. Menyalin dari .env.example...
    copy .env.example .env >nul
    echo [INFO] Edit file .env dan isi APP_PASSWORD sebelum lanjut.
    echo        Buka .env dengan notepad: notepad .env
    echo.
    pause
)

:: Buat virtual environment jika belum ada
if not exist venv (
    echo [INFO] Membuat virtual environment...
    python -m venv venv
)

:: Aktifkan venv
call venv\Scripts\activate.bat

:: Install / update dependencies
echo [INFO] Menginstall dependencies...
pip install -r requirements.txt --quiet

echo.
echo ============================================================
echo   Membuka Cuanmology di browser...
echo   Tekan Ctrl+C untuk menghentikan
echo ============================================================
echo.

:: Jalankan Streamlit
python -m streamlit run web/streamlit_app.py --server.port 8501 --server.headless false

pause
