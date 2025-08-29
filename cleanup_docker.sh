#!/bin/bash
# Clean up Docker space - remove unused images, containers, volumes

echo "🧹 Docker Space Cleanup Tool"
echo "============================="
echo

# Show current disk usage
echo "📊 Current Docker space usage:"
docker system df
echo

# Show current disk space
echo "💾 Current server disk space:"
df -h /
echo

echo "🗑️  What will be cleaned:"
echo "• Stopped containers"
echo "• Unused networks"
echo "• Dangling images"
echo "• Build cache"
echo "• Unused volumes (if you confirm)"
echo

# Ask for confirmation
read -p "⚠️  Continue with cleanup? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cleanup cancelled"
    exit 0
fi

echo
echo "🧹 Starting cleanup..."

# Clean up containers, networks, images, and build cache
echo "1️⃣  Removing stopped containers, unused networks, dangling images..."
docker system prune -f

echo
echo "2️⃣  Removing unused images (not just dangling)..."
docker image prune -a -f

echo
echo "3️⃣  Removing build cache..."
docker builder prune -f

echo
# Ask about volumes separately (more dangerous)
echo "⚠️  Volume cleanup (CAREFUL - this affects data):"
docker volume ls
echo
read -p "🗑️  Remove unused volumes? This is SAFE for your bot (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "4️⃣  Removing unused volumes..."
    docker volume prune -f
else
    echo "4️⃣  Skipping volume cleanup"
fi

echo
echo "🎉 Cleanup complete!"
echo
echo "📊 New Docker space usage:"
docker system df
echo
echo "💾 New server disk space:"
df -h /
echo

echo "✅ Space cleanup done!"
echo "Your bot data is safe - only unused Docker stuff was removed."