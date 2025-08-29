#!/bin/bash
# Docker-based reset script for Digital Ocean
# No Python installation needed - uses the bot container

echo "=================================="
echo "Docker Reset - Last 3 Posts Tool"
echo "=================================="
echo

# Check if Docker is running
if ! docker --version > /dev/null 2>&1; then
    echo "ERROR: Docker not found!"
    exit 1
fi

echo "1. Checking current bot status..."
CONTAINER_STATUS=$(docker ps -q -f name=reddit_feed_bot)
if [ -z "$CONTAINER_STATUS" ]; then
    echo "   Bot container is not running"
    BOT_RUNNING=false
else
    echo "   Bot container is running"
    BOT_RUNNING=true
fi

echo
echo "2. Stopping bot to safely reset database..."
docker-compose down

echo
echo "3. Running reset script using bot container..."
echo "   (This will reset last 3 posts for all channels)"

# Run the reset script inside the bot container
# Mount the database volume so we can modify it
docker run --rm \
    -v "$(pwd)/data:/app/data" \
    -v "$(pwd):/app" \
    -w /app \
    python:3.11-slim \
    python scripts/debug/simple_reset.py

RESET_STATUS=$?

if [ $RESET_STATUS -eq 0 ]; then
    echo
    echo "4. ✅ Reset completed successfully!"
    echo
    echo "5. Starting bot with webhook auto-recreation fixes..."
    docker-compose up -d
    
    echo
    echo "6. 👀 Watch the logs to see reprocessing:"
    echo "   docker logs -f reddit_feed_bot"
    echo
    echo "🎉 Done! Check your Discord channels for reprocessed posts!"
    echo "=================================="
else
    echo
    echo "4. ❌ Reset failed!"
    echo "   Please check the error messages above."
    echo
    echo "5. Restarting bot anyway..."
    docker-compose up -d
    echo "=================================="
fi