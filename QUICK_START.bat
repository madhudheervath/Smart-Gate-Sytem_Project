@echo off
title Smart Gate Pass System - Quick Start
color 0B

REM Quick start for already setup project
if not exist ".venv\" (
    color 0E
    echo.
    echo ============================================================
    echo    FIRST TIME SETUP REQUIRED
    echo ============================================================
    echo.
    echo Please run SETUP.bat first to install everything!
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo    SMART GATE PASS SYSTEM
echo ============================================================
echo.
echo Starting server...
echo.

call .venv\Scripts\activate.bat
cd backend

echo Server running on: http://127.0.0.1:8080
echo.
echo PORTALS:
echo   Student:      http://127.0.0.1:8080/frontend/student/index.html
echo   Admin:        http://127.0.0.1:8080/frontend/admin/index.html
echo   Gate Scanner: http://127.0.0.1:8080/frontend/guard/index.html
echo.
echo Press Ctrl+C to stop the server
echo.

python -m uvicorn app:app --host 127.0.0.1 --port 8080 --reload

