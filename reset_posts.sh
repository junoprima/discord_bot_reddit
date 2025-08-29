#!/bin/bash
# Simple Docker reset for Digital Ocean - No Python installation needed

echo "========================================="
echo "🔄 Reset Last 3 Posts - Docker Version"
echo "========================================="
echo

# Step 1: Check if bot is running
echo "1️⃣  Checking bot status..."
if docker ps | grep -q reddit_feed_bot; then
    echo "   ✅ Bot container found"
    CONTAINER_EXISTS=true
else
    echo "   ℹ️  Bot container not running (that's ok)"
    CONTAINER_EXISTS=false
fi

# Step 2: Stop bot safely
echo
echo "2️⃣  Stopping bot to reset database..."
docker-compose down
sleep 2

# Step 3: Run reset using temporary container
echo
echo "3️⃣  Running reset script..."
echo "   (This resets last 3 posts for all channels)"
echo

# Use a temporary Python container to run our reset script
# Mount the data directory and the script
docker run --rm \
    -v "$(pwd)/data:/data" \
    -v "$(pwd)/scripts:/scripts" \
    -w /data \
    python:3.11-slim \
    bash -c "
        echo 'Installing requirements...'
        pip install sqlite3 > /dev/null 2>&1 || echo 'sqlite3 already available'
        echo 'Running reset script...'
        python /scripts/debug/simple_reset.py
    "

# Step 4: Start bot with fixes
echo
echo "4️⃣  Starting bot with webhook auto-recreation..."
docker-compose up -d

echo
echo "5️⃣  Checking if bot started..."
sleep 3
if docker ps | grep -q reddit_feed_bot; then
    echo "   ✅ Bot is running!"
else
    echo "   ⚠️  Bot might be starting... check with: docker ps"
fi

echo
echo "========================================="
echo "🎉 DONE! What happens next:"
echo "• Bot will reprocess last ~3 posts per channel"
echo "• Broken webhooks will be auto-recreated" 
echo "• Missing posts will appear in Discord"
echo "• Watch with: docker logs -f reddit_feed_bot"
echo "========================================="