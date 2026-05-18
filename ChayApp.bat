@echo off
chcp 65001 >nul
title Gym Progress Tracker AI
cd /d "%~dp0"

echo.
echo  Gym Progress Tracker AI
echo  Dang khoi dong...
echo.

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo  [Goi y] Chua co .venv — dung Python he thong.
    echo  Lan dau: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    echo.
)

start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8501"
python -m streamlit run app.py
if errorlevel 1 (
    echo.
    echo  Loi: chua cai thu vien. Chay lenh sau trong thu muc nay:
    echo    pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

pause
