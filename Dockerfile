# Multi-stage Dockerfile for PMMP Pro-G4
# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Copy only requirements first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies into user site-packages
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime - Minimal image
FROM python:3.11-slim

LABEL maintainer="Loose Nutz Garage"
LABEL description="PMMP Pro-G4 - Vehicle Diagnostics System with RAG"
LABEL version="1.0.0"

WORKDIR /app

# Create application user (non-root)
RUN useradd -m -u 1000 -s /bin/bash appuser

# Copy installed dependencies from builder
COPY --from=builder /root/.local /root/.local

# Set PATH to use installed packages
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/config && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser . .

# Security: Switch to non-root user
USER appuser

# Health check - verify application starts and responds
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Expose ports (for future REST API)
EXPOSE 8080 9090

# Default environment
ENV PMMP_ENV=production

# Run application
CMD ["python", "-m", "main"]
