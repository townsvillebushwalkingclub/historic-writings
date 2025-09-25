# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    tk-dev \
    tcl-dev \
    cron \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY pdf_ocr_gemini.py .
COPY README.md .

# Create necessary directories
RUN mkdir -p /app/pdfs /app/ocr_output /app/logs

# Create entrypoint script
RUN echo '#!/bin/bash' > /app/entrypoint.sh && \
    echo 'set -e' >> /app/entrypoint.sh && \
    echo '' >> /app/entrypoint.sh && \
    echo '# Function to run OCR with logging' >> /app/entrypoint.sh && \
    echo 'run_ocr() {' >> /app/entrypoint.sh && \
    echo '    echo "$(date): Starting PDF OCR processing..." | tee -a /app/logs/ocr.log' >> /app/entrypoint.sh && \
    echo '    cd /app' >> /app/entrypoint.sh && \
    echo '    /usr/local/bin/python3 pdf_ocr_gemini.py 2>&1 | tee -a /app/logs/ocr.log' >> /app/entrypoint.sh && \
    echo '    exit_code=${PIPESTATUS[0]}' >> /app/entrypoint.sh && \
    echo '    if [ $exit_code -eq 0 ]; then' >> /app/entrypoint.sh && \
    echo '        echo "$(date): OCR processing completed successfully" | tee -a /app/logs/ocr.log' >> /app/entrypoint.sh && \
    echo '    else' >> /app/entrypoint.sh && \
    echo '        echo "$(date): OCR processing failed with exit code $exit_code" | tee -a /app/logs/ocr.log' >> /app/entrypoint.sh && \
    echo '    fi' >> /app/entrypoint.sh && \
    echo '}' >> /app/entrypoint.sh && \
    echo '' >> /app/entrypoint.sh && \
    echo '# Check if running mode is specified' >> /app/entrypoint.sh && \
    echo 'if [ "$1" = "cron" ]; then' >> /app/entrypoint.sh && \
    echo '    echo "$(date): Setting up cron job to run every hour..." | tee -a /app/logs/ocr.log' >> /app/entrypoint.sh && \
    echo '    # Create cron job that runs every hour' >> /app/entrypoint.sh && \
    echo '    echo "0 * * * * /app/entrypoint.sh run >> /app/logs/cron.log 2>&1" | crontab -' >> /app/entrypoint.sh && \
    echo '    # Run once immediately' >> /app/entrypoint.sh && \
    echo '    run_ocr' >> /app/entrypoint.sh && \
    echo '    # Start cron daemon in foreground' >> /app/entrypoint.sh && \
    echo '    echo "$(date): Starting cron daemon..." | tee -a /app/logs/ocr.log' >> /app/entrypoint.sh && \
    echo '    cron -f' >> /app/entrypoint.sh && \
    echo 'elif [ "$1" = "run" ]; then' >> /app/entrypoint.sh && \
    echo '    # Just run OCR once' >> /app/entrypoint.sh && \
    echo '    run_ocr' >> /app/entrypoint.sh && \
    echo 'else' >> /app/entrypoint.sh && \
    echo '    # Default: run OCR once and exit' >> /app/entrypoint.sh && \
    echo '    run_ocr' >> /app/entrypoint.sh && \
    echo 'fi' >> /app/entrypoint.sh

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=Australia/Brisbane
ENV TZDIR=/usr/share/zoneinfo

# Expose volume mount points
VOLUME ["/app/pdfs", "/app/ocr_output", "/app/logs"]

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["cron"]
