# Use Python 3.14 slim image
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY fortress/ ./fortress/
COPY config/ ./config/
COPY setup.py .
COPY pyproject.toml .

# Install the package in development mode
RUN pip install -e .

# Create necessary directories
RUN mkdir -p logs data

# Create non-root user
RUN groupadd -r fortress && useradd -r -g fortress fortress
RUN chown -R fortress:fortress /app
USER fortress

# Expose ports
EXPOSE 8001 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/api/status || exit 1

# Start command
CMD ["python", "-m",
