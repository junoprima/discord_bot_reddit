# Migration Plan: Firestore to SQLite + Dev to Production

## 🎯 Goal
Migrate from Firestore (main branch) to SQLite (dev branch) and promote dev branch to production with zero downtime.

## 📋 Pre-Migration Checklist

1. **Backup current production data**
2. **Test migration script locally**
3. **Verify all Discord channels continue working**

## 🔄 Migration Steps

### Step 1: Prepare Migration Environment
```bash
# On your DigitalOcean server
cd ~/projects/reddit_bot_dev

# Pull latest dev branch
git pull origin dev

# Install dependencies (including firebase-admin)
pip install -r requirements.txt
```

### Step 2: Run Data Migration
```bash
# Make sure your .env has FIREBASE_CREDENTIALS path
# Run migration script
python migrate_firestore_to_sqlite.py
```

### Step 3: Test New SQLite Bot
```bash
# Stop old Firestore bot temporarily
docker stop reddit_feed_bot

# Start new SQLite bot
docker-compose up -d --build

# Check logs - should show migrated channels
docker logs reddit_feed_bot_dev -f

# Verify your Discord channels still work
# Test /subscribe and other commands
```

### Step 4: Branch Promotion (Zero Downtime)
```bash
# Create backup of main branch
git checkout main
git checkout -b main-firestore-backup
git push origin main-firestore-backup

# Promote dev to main
git checkout main
git reset --hard dev
git push origin main --force-with-lease

# Update production container
docker stop reddit_feed_bot
docker rm reddit_feed_bot
docker build -t reddit_feed_bot .
docker run -d --name reddit_feed_bot --env-file .env reddit_feed_bot
```

### Step 5: Cleanup
```bash
# Remove old dev container
docker stop reddit_feed_bot_dev
docker rm reddit_feed_bot_dev

# Clean up old images
docker image prune -f
```

## 🔍 Verification Checklist

- [ ] All Discord channels show up in logs
- [ ] Slash commands work (`/subscribe`, `/unsubscribe`, etc.)
- [ ] Reddit posts are being fetched and posted
- [ ] No permission errors in logs
- [ ] Database file exists at `data/reddit_bot.db`

## 🚨 Rollback Plan

If something goes wrong:
```bash
# Restore main branch
git checkout main
git reset --hard main-firestore-backup
git push origin main --force-with-lease

# Restart old bot
docker build -t reddit_feed_bot .
docker run -d --name reddit_feed_bot --env-file .env reddit_feed_bot
```

## 📊 Expected Results

- **Zero downtime** for Discord users
- **All existing channels preserved**
- **Better performance** with SQLite
- **Cleaner architecture** with modular design
- **Easier maintenance** going forward

## 🎉 Post-Migration Benefits

1. **No more Firestore costs**
2. **Faster local database operations**  
3. **Better error handling and logging**
4. **Improved webhook management**
5. **More reliable duplicate detection**