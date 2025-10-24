@echo off
setlocal enabledelayedexpansion
title Smart Gate Pass System - One-Click Setup
color 0A

echo.
echo ============================================================
echo    SMART GATE PASS SYSTEM - AUTOMATIC SETUP
echo ============================================================
echo.
echo This will install and configure everything automatically.
echo Please wait...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.11 or 3.12 from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [1/7] Python detected:
python --version
echo.

REM Check if virtual environment exists
if exist ".venv\" (
    echo [2/7] Virtual environment already exists. Activating...
) else (
    echo [2/7] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        color 0C
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call .venv\Scripts\activate.bat
if errorlevel 1 (
    color 0C
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)

echo [3/7] Upgrading pip and tools...
python -m pip install --upgrade pip setuptools wheel --quiet
if errorlevel 1 (
    color 0E
    echo [WARNING] pip upgrade had issues, continuing...
)

echo [4/7] Installing Python dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    color 0C
    echo [ERROR] Failed to install dependencies!
    echo.
    echo Trying with compatible versions...
    pip uninstall -y pydantic pydantic-core pydantic-settings
    pip install "pydantic==2.5.0" "pydantic-core==2.14.6" "pydantic-settings==2.1.0"
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Still failed. Please check your internet connection.
        pause
        exit /b 1
    )
)

echo [5/7] Setting up database...
cd backend

REM Check if database needs initialization
if not exist "gatepass.db" (
    echo      Creating new database...
) else (
    echo      Database exists, running migrations...
)

python migrate_db.py >nul 2>&1
python migrate_entry_exit.py >nul 2>&1

echo [6/7] Seeding initial data...
python seed.py >nul 2>&1
if errorlevel 1 (
    echo      [WARNING] Seed data might already exist, continuing...
)

python add_students.py >nul 2>&1
if errorlevel 1 (
    echo      [WARNING] Student data might already exist, continuing...
)

cd ..

echo [7/7] Setup complete!
echo.
color 0A
echo ============================================================
echo    SETUP SUCCESSFUL!
echo ============================================================
echo.
echo Default Accounts:
echo.
echo   GATE SCANNER:
echo   - Email:    scanner@uni.edu
echo   - Password: scanner123
echo.
echo   SAMPLE STUDENT:
echo   - Email:    u22cn421@cmrtc.ac.in
echo   - Password: tharun123
echo.
echo ============================================================
echo.
echo Starting server...
echo.

REM Start the server
cd backend
echo Server will start on: http://127.0.0.1:8080
echo.
echo PORTALS:
echo   Student:      http://127.0.0.1:8080/frontend/student/index.html
echo   Admin:        http://127.0.0.1:8080/frontend/admin/index.html
echo   Gate Scanner: http://127.0.0.1:8080/frontend/guard/index.html
echo.
echo Press Ctrl+C to stop the server
echo.
python -m uvicorn app:app --host 127.0.0.1 --port 8080 --reload

