#!/usr/bin/env python3
"""
Migration script to convert Firestore data to SQLite for Discord Reddit Bot
Migrates channel configs and sent post IDs from Firestore to local SQLite database.
"""

import asyncio
import logging
import os
from typing import Dict, List
import aiosqlite
from firebase_admin import credentials, firestore, initialize_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Firebase credentials
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")
if not FIREBASE_CREDENTIALS:
    print("❌ Error: FIREBASE_CREDENTIALS not found in .env file")
    exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class FirestoreToSQLiteMigrator:
    """Handles migration from Firestore to SQLite"""
    
    def __init__(self, sqlite_db_path: str = "data/reddit_bot.db"):
        self.sqlite_db_path = sqlite_db_path
        self.firestore_client = None
        
    async def initialize_firebase(self):
        """Initialize Firebase connection"""
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
            initialize_app(cred)
            self.firestore_client = firestore.client()
            logger.info("✅ Firebase initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firebase: {e}")
            raise
    
    async def create_sqlite_tables(self):
        """Create SQLite tables if they don't exist"""
        os.makedirs(os.path.dirname(self.sqlite_db_path), exist_ok=True)
        
        async with aiosqlite.connect(self.sqlite_db_path) as db:
            # Create channel_configs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channel_configs (
                    channel_id TEXT PRIMARY KEY,
                    subreddit TEXT NOT NULL,
                    webhook_url TEXT NOT NULL,
                    bot_name TEXT,
                    bot_avatar TEXT,
                    last_post_id TEXT,
                    last_post_timestamp REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create sent_post_ids table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sent_post_ids (
                    channel_id TEXT,
                    post_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (channel_id, post_id)
                )
            """)
            
            # Create index for faster queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sent_posts_channel 
                ON sent_post_ids(channel_id, created_at)
            """)
            
            await db.commit()
            logger.info("✅ SQLite tables created successfully")
    
    async def migrate_channel_configs(self) -> int:
        """Migrate channel configurations from Firestore to SQLite"""
        migrated_count = 0
        
        try:
            # Get all channel configs from Firestore
            configs = self.firestore_client.collection("channel_configs").stream()
            
            async with aiosqlite.connect(self.sqlite_db_path) as db:
                for config in configs:
                    data = config.to_dict()
                    channel_id = data.get("channel_id")
                    
                    if not channel_id:
                        logger.warning(f"⚠️ Skipping config without channel_id: {config.id}")
                        continue
                    
                    # Prepare data for SQLite
                    sqlite_data = {
                        "channel_id": channel_id,
                        "subreddit": data.get("subreddit", ""),
                        "webhook_url": data.get("webhook_url", ""),
                        "bot_name": data.get("bot_name"),
                        "bot_avatar": data.get("bot_avatar"),
                        "last_post_id": data.get("last_post_id"),
                        "last_post_timestamp": float(data.get("last_post_timestamp", 0))
                    }
                    
                    # Insert into SQLite
                    await db.execute("""
                        INSERT OR REPLACE INTO channel_configs 
                        (channel_id, subreddit, webhook_url, bot_name, bot_avatar, 
                         last_post_id, last_post_timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sqlite_data["channel_id"],
                        sqlite_data["subreddit"],
                        sqlite_data["webhook_url"],
                        sqlite_data["bot_name"],
                        sqlite_data["bot_avatar"],
                        sqlite_data["last_post_id"],
                        sqlite_data["last_post_timestamp"]
                    ))
                    
                    migrated_count += 1
                    logger.info(f"✅ Migrated channel {channel_id} (r/{sqlite_data['subreddit']})")
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"❌ Error migrating channel configs: {e}")
            raise
        
        return migrated_count
    
    async def migrate_sent_post_ids(self) -> int:
        """Migrate sent post IDs from Firestore to SQLite"""
        migrated_count = 0
        
        try:
            # Get all sent_post_ids from Firestore
            sent_posts = self.firestore_client.collection("sent_post_ids").stream()
            
            async with aiosqlite.connect(self.sqlite_db_path) as db:
                for sent_post in sent_posts:
                    channel_id = sent_post.id
                    data = sent_post.to_dict()
                    post_ids = data.get("post_ids", [])
                    
                    logger.info(f"📝 Migrating {len(post_ids)} post IDs for channel {channel_id}")
                    
                    for post_id in post_ids:
                        try:
                            await db.execute("""
                                INSERT OR IGNORE INTO sent_post_ids (channel_id, post_id)
                                VALUES (?, ?)
                            """, (channel_id, post_id))
                            migrated_count += 1
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to insert post {post_id} for channel {channel_id}: {e}")
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"❌ Error migrating sent post IDs: {e}")
            raise
        
        return migrated_count
    
    async def verify_migration(self):
        """Verify migration results"""
        async with aiosqlite.connect(self.sqlite_db_path) as db:
            # Count channel configs
            async with db.execute("SELECT COUNT(*) FROM channel_configs") as cursor:
                channel_count = (await cursor.fetchone())[0]
            
            # Count sent post IDs
            async with db.execute("SELECT COUNT(*) FROM sent_post_ids") as cursor:
                post_count = (await cursor.fetchone())[0]
            
            # Show sample data
            async with db.execute("SELECT channel_id, subreddit FROM channel_configs LIMIT 5") as cursor:
                sample_channels = await cursor.fetchall()
            
            logger.info("📊 Migration Results:")
            logger.info(f"  • Channel configs: {channel_count}")
            logger.info(f"  • Sent post IDs: {post_count}")
            logger.info("📋 Sample channels:")
            for channel_id, subreddit in sample_channels:
                logger.info(f"  • {channel_id} → r/{subreddit}")
    
    async def run_migration(self):
        """Run the complete migration process"""
        logger.info("🚀 Starting Firestore to SQLite migration...")
        
        # Initialize Firebase
        await self.initialize_firebase()
        
        # Create SQLite tables
        await self.create_sqlite_tables()
        
        # Migrate channel configs
        logger.info("📦 Migrating channel configurations...")
        channel_count = await self.migrate_channel_configs()
        
        # Migrate sent post IDs
        logger.info("🔄 Migrating sent post IDs...")
        post_count = await self.migrate_sent_post_ids()
        
        # Verify migration
        await self.verify_migration()
        
        logger.info("✅ Migration completed successfully!")
        logger.info(f"📈 Summary: {channel_count} channels, {post_count} post IDs migrated")
        
        return {
            "channels_migrated": channel_count,
            "posts_migrated": post_count
        }

async def main():
    """Main migration function"""
    migrator = FirestoreToSQLiteMigrator()
    
    try:
        results = await migrator.run_migration()
        print("\n" + "="*50)
        print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print(f"📊 Channels migrated: {results['channels_migrated']}")
        print(f"📊 Post IDs migrated: {results['posts_migrated']}")
        print("="*50)
        
    except Exception as e:
        logger.error(f"💥 Migration failed: {e}")
        print("\n" + "="*50)
        print("❌ MIGRATION FAILED!")
        print(f"Error: {e}")
        print("="*50)
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)