# Multi-stage Dockerfile for production
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    pkg-config \
    libsystemd-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies including cron, curl, and libgomp for LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app /app/data /app/models /app/logs && \
    chown -R appuser:appuser /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Set environment
ENV PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser migrations/ ./migrations/
COPY --chown=appuser:appuser alembic.ini .env* ./

# Create necessary directories
RUN mkdir -p /app/data/analytics /app/models/social /app/logs

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

EXPOSE 5000

# Default command: Uvicorn for API
CMD ["uvicorn", "src.monitoring:app", "--host", "0.0.0.0", "--port", "8000"]
