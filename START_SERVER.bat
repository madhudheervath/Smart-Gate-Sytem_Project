@echo off
echo ================================
echo  Smart Gate - Starting Server
echo ================================
echo.

cd backend

REM Check if virtual environment exists
if not exist ".venv\" (
    echo Creating virtual environment...
    python -m venv .venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
echo.

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
echo.

REM Run seed script
echo Seeding database with demo users...
python seed.py
echo.

REM Start server
echo Starting FastAPI server...
echo Backend will be available at: http://localhost:8080
echo API docs at: http://localhost:8080/docs
echo.
echo Press Ctrl+C to stop the server
echo.
uvicorn app:app --reload --port 8080

pause

