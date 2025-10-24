#!/bin/bash

echo "================================"
echo " Smart Gate - Starting Server"
echo "================================"
echo ""

cd backend

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo ""

# Run seed script
echo "Seeding database with demo users..."
python seed.py
echo ""

# Start server
echo "Starting FastAPI server..."
echo "Backend will be available at: http://localhost:8080"
echo "API docs at: http://localhost:8080/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
uvicorn app:app --reload --port 8080

