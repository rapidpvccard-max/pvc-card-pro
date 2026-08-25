# Production Dockerfile for PVC Card Pro with Playwright Chromium pre-installed
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Install system dependencies & build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libzbar0 \
    tesseract-ocr \
    fontconfig \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-noto-extra \
    fonts-indic \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure Playwright browser binaries are ready
RUN playwright install chromium

# Copy application files
COPY . .

# Ensure upload/output/renders directories exist
RUN mkdir -p uploads output static/renders

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV ENVIRONMENT=production

EXPOSE 8000

# Start production server
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
