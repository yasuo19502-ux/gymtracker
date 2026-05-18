@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Push len GitHub
cd /d "%~dp0"

echo.
echo  === Push Gym Tracker len GitHub ===
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo  Chua cai Git. Tai: https://git-scm.com/download/win
    pause
    exit /b 1
)

git status >nul 2>&1
if errorlevel 1 (
    echo  Chua co repo Git trong thu muc nay.
    pause
    exit /b 1
)

set /p REPO_URL="Dan URL repo GitHub (vd https://github.com/ban/ten-repo.git): "
if "!REPO_URL!"=="" (
    echo  Huy.
    pause
    exit /b 1
)

REM --- Kiem tra ten / email (bat buoc truoc commit) ---
set "CFG_NAME="
set "CFG_EMAIL="
for /f "delims=" %%a in ('git config --get user.name 2^>nul') do set "CFG_NAME=%%a"
for /f "delims=" %%a in ('git config --get user.email 2^>nul') do set "CFG_EMAIL=%%a"

if "!CFG_NAME!"=="" (
    echo.
    set /p GIT_NAME="Ten hien thi Git ^(vd Long hoac ten GitHub^): "
    if "!GIT_NAME!"=="" (
        echo  Loi: Ten khong duoc de trong.
        pause
        exit /b 1
    )
    git config user.name "!GIT_NAME!"
)

if "!CFG_EMAIL!"=="" (
    echo.
    set /p GIT_EMAIL="Email Git ^(email GitHub hoac xxx@users.noreply.github.com^): "
    if "!GIT_EMAIL!"=="" (
        echo  Loi: Email khong duoc de trong.
        pause
        exit /b 1
    )
    git config user.email "!GIT_EMAIL!"
)

echo.
echo  Git: !CFG_NAME!
for /f "delims=" %%a in ('git config --get user.name') do echo  Ten: %%a
for /f "delims=" %%a in ('git config --get user.email') do echo  Email: %%a

REM --- Stage tat ca file ---
git add -A

REM --- Commit neu chua co ---
git rev-parse HEAD >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Dang tao commit dau tien...
    git commit -m "Initial commit: Gym Progress Tracker AI"
    if errorlevel 1 (
        echo.
        echo  Commit that bai. Kiem tra ten/email o tren.
        pause
        exit /b 1
    )
) else (
    git diff --cached --quiet
    if errorlevel 1 (
        echo.
        echo  Co thay doi moi — tao commit...
        git commit -m "Update Gym Progress Tracker AI"
        if errorlevel 1 (
            echo  Commit that bai.
            pause
            exit /b 1
        )
    )
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin "!REPO_URL!"
) else (
    git remote set-url origin "!REPO_URL!"
)

git branch -M main

echo.
echo  Dang push len GitHub...
git push -u origin main

if errorlevel 1 (
    echo.
    echo  Push that bai. Thu:
    echo   1. Dang nhap GitHub trong trinh duyet khi Git hoi
    echo   2. Hoac dung Personal Access Token thay mat khau
    echo   3. Repo tren GitHub da tao va URL dung
    echo.
    echo  Neu commit da OK, thu lai: git push -u origin main
    echo  Xem: DEPLOY.md
) else (
    echo.
    echo  Push thanh cong!
    echo  Tiep theo: https://share.streamlit.io - Main file: app.py
)

echo.
pause
endlocal
