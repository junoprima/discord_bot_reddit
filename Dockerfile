FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN useradd -m -u 1000 botuser

# Copy application code
COPY config/ ./config/
COPY database/ ./database/
COPY services/ ./services/
COPY utils/ ./utils/
COPY bot.py ./bot.py

# Create necessary directories and set permissions
RUN mkdir -p /app/logs /app/data && chown -R botuser:botuser /app
USER botuser

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/app/data/reddit_bot.db').execute('SELECT 1')" || exit 1

# Run the bot
CMD ["python", "bot.py"]