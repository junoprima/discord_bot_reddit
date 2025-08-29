FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies with fixed package sources
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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
COPY migrate_firestore_to_sqlite.py ./migrate_firestore_to_sqlite.py
COPY verify_migration.py ./verify_migration.py
COPY show_current_settings.py ./show_current_settings.py
COPY check_firestore_simple.py ./check_firestore_simple.py

# Create necessary directories and set permissions
RUN mkdir -p /app/logs /app/data && \
    chown -R botuser:botuser /app && \
    chmod -R 755 /app/logs /app/data
USER botuser

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/app/data/reddit_bot.db').execute('SELECT 1')" || exit 1

# Run the bot
CMD ["python", "bot.py"]