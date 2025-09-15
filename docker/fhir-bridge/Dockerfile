# FHIR Bridge Service Dockerfile
# Provides FHIR R4 integration with EHR systems

FROM python:3.11-slim-bookworm

# Security: Run as non-root user
RUN groupadd -r fhir && useradd -r -g fhir fhir

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

# Install Python dependencies for FHIR
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn \
    aiohttp \
    fhirclient \
    python-dotenv \
    cryptography

# Copy FHIR integration code
COPY src/services/fhir_client.py ./services/fhir_client.py
COPY src/core/security.py ./core/security.py
COPY src/integrations/fhir/ ./integrations/fhir/

# Create necessary directories
RUN mkdir -p /app/logs && \
    chown -R fhir:fhir /app

# Switch to non-root user
USER fhir

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose port
EXPOSE 8080

# Run the FHIR bridge service
CMD ["uvicorn", "integrations.fhir.main:app", "--host", "0.0.0.0", "--port", "8080"]
