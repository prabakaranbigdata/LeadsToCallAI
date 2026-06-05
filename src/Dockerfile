# Use the official slim Python image for a lightweight footprint
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies if needed, then clean up to keep image small
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements first to leverage Docker caching layers
COPY requirements.txt .

# Install dependencies directly into the container environment
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application source code
COPY . .

# Cloud Run dynamically assigns a port via the PORT environment variable (defaults to 8080)
EXPOSE 8080

# Run Uvicorn bound to 0.0.0.0 and the port specified by Cloud Run
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]