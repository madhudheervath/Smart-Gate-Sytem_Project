# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install only the lightweight runtime dependencies needed by the server.
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# We copy requirements first to leverage Docker cache
COPY backend/requirements.txt .

# Keep any fallback wheel build single-threaded to reduce memory pressure
ENV MAX_JOBS=1

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory
COPY backend/ .
COPY frontend/ ../frontend/

# Create a non-root user for security (optional but recommended for Render)
# Create a non-root user for security (optional but recommended for Render)
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose the Render default web port
EXPOSE 10000

# Command to run the application
CMD ["sh", "-c", "python bootstrap.py && uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
