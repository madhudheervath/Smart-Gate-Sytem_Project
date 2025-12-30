# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies required for dlib and opencv
# cmake & g++ are strictly needed for building dlib from source
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# We copy requirements first to leverage Docker cache
COPY backend/requirements.txt .

# Increase timeout for dlib compilation & Reduce memory usage
# Limit compilation to 1 thread to avoid OOM on free tier
ENV CMAKE_BUILD_PARALLEL_LEVEL=1
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

# Expose the port
EXPOSE 8080

# Command to run the application
CMD ["sh", "-c", "python seed.py && uvicorn app:app --host 0.0.0.0 --port 8080"]
