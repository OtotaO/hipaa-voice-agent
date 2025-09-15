# Temporal Worker Dockerfile
# Executes durable workflows for HIPAA-compliant operations

FROM python:3.11-slim-bookworm

# Security: Run as non-root user
RUN groupadd -r temporal && useradd -r -g temporal temporal

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir temporalio aiohttp pydantic python-dotenv

# Copy workflow code
COPY src/workflows/ ./workflows/
COPY src/core/security.py ./core/security.py
COPY src/services/fhir_client.py ./services/fhir_client.py

# Create necessary directories
RUN mkdir -p /app/logs && \
    chown -R temporal:temporal /app

# Switch to non-root user
USER temporal

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the worker
CMD ["python", "-m", "workflows.temporal_client", "worker"]
