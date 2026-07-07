# Use Python 3.11 slim
FROM python:3.11-slim

# --- Environment ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Set working directory
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    tesseract-ocr \
    poppler-utils \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    fonts-liberation \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libx11-xcb1 \
    libxt6 \
    && rm -rf /var/lib/apt/lists/*

COPY ml/requirements.txt .

# Install python deps (use pip cache mount when building with BuildKit)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Prepare Playwright browser install directory
RUN mkdir -p /ms-playwright && chmod 777 /ms-playwright

RUN playwright install chromium

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app /ms-playwright

# Prepare cache directory for camoufox and fetch browser data
RUN mkdir -p /home/appuser/.cache && chown -R appuser:appuser /home/appuser/.cache
USER appuser
RUN python -m camoufox fetch
USER root

# Copy application code
COPY ml/src/ ./src/
COPY ml/config/ ./config/
COPY ml/yahoo_finance_tickers.json .

# Expose port
EXPOSE 8000

# Switch to non-root user for runtime security
USER appuser

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

# Start the app
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
