# Pipecat Service Dockerfile
# HIPAA-compliant configuration with security hardening

FROM python:3.11-slim-bookworm AS base

# Security: Run as non-root user
RUN groupadd -r pipecat && useradd -r -g pipecat pipecat

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    cmake \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libasound2-dev \
    portaudio19-dev \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/certs /app/temp && \
    chown -R pipecat:pipecat /app

# Security: Remove unnecessary files and tools
RUN apt-get purge -y --auto-remove gcc g++ make cmake && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Switch to non-root user
USER pipecat

# Environment variables for security
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Expose ports (WebSocket and health check)
EXPOSE 8080 8081

# Run the application
CMD ["python", "-m", "uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--access-log", \
     "--log-config", "/app/config/logging.yaml"]
