#!/usr/bin/env python3
"""
Verification script to compare Firestore and SQLite data
Ensures all channel configurations and post IDs were migrated correctly.
"""

import asyncio
import logging
import os
import aiosqlite
from firebase_admin import credentials, firestore, initialize_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class MigrationVerifier:
    """Verifies migration completeness and accuracy"""
    
    def __init__(self, sqlite_db_path: str = "data/reddit_bot.db"):
        self.sqlite_db_path = sqlite_db_path
        self.firestore_client = None
        
    async def initialize_firebase(self):
        """Initialize Firebase connection"""
        try:
            firebase_creds = os.getenv("FIREBASE_CREDENTIALS")
            if not firebase_creds:
                logger.error("❌ FIREBASE_CREDENTIALS not found in .env")
                return False
                
            cred = credentials.Certificate(firebase_creds)
            initialize_app(cred)
            self.firestore_client = firestore.client()
            logger.info("✅ Firebase initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Firebase initialization failed: {e}")
            return False
    
    async def get_firestore_data(self):
        """Get all data from Firestore"""
        firestore_data = {
            "channel_configs": {},
            "sent_post_ids": {}
        }
        
        try:
            # Get channel configs
            configs = self.firestore_client.collection("channel_configs").stream()
            for config in configs:
                data = config.to_dict()
                channel_id = data.get("channel_id")
                if channel_id:
                    firestore_data["channel_configs"][channel_id] = data
            
            # Get sent post IDs
            sent_posts = self.firestore_client.collection("sent_post_ids").stream()
            for sent_post in sent_posts:
                channel_id = sent_post.id
                data = sent_post.to_dict()
                firestore_data["sent_post_ids"][channel_id] = data.get("post_ids", [])
            
            logger.info(f"📊 Firestore: {len(firestore_data['channel_configs'])} channels, "
                       f"{sum(len(posts) for posts in firestore_data['sent_post_ids'].values())} post IDs")
            
        except Exception as e:
            logger.error(f"❌ Error reading Firestore: {e}")
        
        return firestore_data
    
    async def get_sqlite_data(self):
        """Get all data from SQLite"""
        sqlite_data = {
            "channel_configs": {},
            "sent_post_ids": {}
        }
        
        try:
            if not os.path.exists(self.sqlite_db_path):
                logger.warning("⚠️ SQLite database not found")
                return sqlite_data
                
            async with aiosqlite.connect(self.sqlite_db_path) as db:
                db.row_factory = aiosqlite.Row
                
                # Get channel configs
                async with db.execute("SELECT * FROM channel_configs") as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        sqlite_data["channel_configs"][row["channel_id"]] = dict(row)
                
                # Get sent post IDs grouped by channel
                async with db.execute("""
                    SELECT channel_id, GROUP_CONCAT(post_id) as post_ids
                    FROM sent_post_ids 
                    GROUP BY channel_id
                """) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        post_ids = row["post_ids"].split(",") if row["post_ids"] else []
                        sqlite_data["sent_post_ids"][row["channel_id"]] = post_ids
                
                logger.info(f"📊 SQLite: {len(sqlite_data['channel_configs'])} channels, "
                           f"{sum(len(posts) for posts in sqlite_data['sent_post_ids'].values())} post IDs")
                
        except Exception as e:
            logger.error(f"❌ Error reading SQLite: {e}")
        
        return sqlite_data
    
    async def compare_channel_configs(self, firestore_data, sqlite_data):
        """Compare channel configurations"""
        fs_channels = firestore_data["channel_configs"]
        sql_channels = sqlite_data["channel_configs"]
        
        logger.info("\n🔍 Comparing Channel Configurations:")
        logger.info("=" * 50)
        
        # Check if all Firestore channels exist in SQLite
        missing_in_sqlite = []
        for channel_id, fs_config in fs_channels.items():
            if channel_id not in sql_channels:
                missing_in_sqlite.append(channel_id)
                continue
                
            sql_config = sql_channels[channel_id]
            
            # Compare key fields
            comparisons = [
                ("subreddit", fs_config.get("subreddit"), sql_config.get("subreddit")),
                ("webhook_url", fs_config.get("webhook_url"), sql_config.get("webhook_url")),
                ("bot_name", fs_config.get("bot_name"), sql_config.get("bot_name")),
                ("bot_avatar", fs_config.get("bot_avatar"), sql_config.get("bot_avatar")),
                ("last_post_id", fs_config.get("last_post_id"), sql_config.get("last_post_id")),
                ("last_post_timestamp", fs_config.get("last_post_timestamp"), sql_config.get("last_post_timestamp")),
            ]
            
            differences = []
            for field, fs_val, sql_val in comparisons:
                if str(fs_val) != str(sql_val):
                    differences.append(f"{field}: '{fs_val}' → '{sql_val}'")
            
            if differences:
                logger.warning(f"⚠️ Channel {channel_id} has differences:")
                for diff in differences:
                    logger.warning(f"    {diff}")
            else:
                logger.info(f"✅ Channel {channel_id} (r/{fs_config.get('subreddit')}) - Perfect match")
        
        if missing_in_sqlite:
            logger.error(f"❌ {len(missing_in_sqlite)} channels missing in SQLite:")
            for channel_id in missing_in_sqlite:
                subreddit = fs_channels[channel_id].get("subreddit", "unknown")
                logger.error(f"    {channel_id} (r/{subreddit})")
        
        # Check for extra channels in SQLite
        extra_in_sqlite = [cid for cid in sql_channels if cid not in fs_channels]
        if extra_in_sqlite:
            logger.info(f"ℹ️ {len(extra_in_sqlite)} extra channels in SQLite (possibly new):")
            for channel_id in extra_in_sqlite:
                subreddit = sql_channels[channel_id].get("subreddit", "unknown")
                logger.info(f"    {channel_id} (r/{subreddit})")
        
        return len(missing_in_sqlite) == 0
    
    async def compare_sent_post_ids(self, firestore_data, sqlite_data):
        """Compare sent post IDs"""
        fs_posts = firestore_data["sent_post_ids"]
        sql_posts = sqlite_data["sent_post_ids"]
        
        logger.info("\n🔍 Comparing Sent Post IDs:")
        logger.info("=" * 50)
        
        total_fs_posts = sum(len(posts) for posts in fs_posts.values())
        total_sql_posts = sum(len(posts) for posts in sql_posts.values())
        
        logger.info(f"📊 Firestore: {total_fs_posts} total post IDs across {len(fs_posts)} channels")
        logger.info(f"📊 SQLite: {total_sql_posts} total post IDs across {len(sql_posts)} channels")
        
        missing_channels = 0
        missing_posts = 0
        
        for channel_id, fs_post_list in fs_posts.items():
            if channel_id not in sql_posts:
                missing_channels += 1
                logger.error(f"❌ Channel {channel_id}: No post IDs migrated ({len(fs_post_list)} missing)")
                continue
            
            sql_post_list = sql_posts[channel_id]
            fs_set = set(fs_post_list)
            sql_set = set(sql_post_list)
            
            missing = fs_set - sql_set
            if missing:
                missing_posts += len(missing)
                logger.warning(f"⚠️ Channel {channel_id}: {len(missing)} post IDs missing")
            else:
                logger.info(f"✅ Channel {channel_id}: All {len(fs_post_list)} post IDs migrated")
        
        return missing_channels == 0 and missing_posts == 0
    
    async def verify_migration(self):
        """Run complete verification"""
        logger.info("🔍 Starting Migration Verification...")
        logger.info("=" * 60)
        
        # Initialize Firebase
        if not await self.initialize_firebase():
            return False
        
        # Get data from both sources
        logger.info("📡 Fetching Firestore data...")
        firestore_data = await self.get_firestore_data()
        
        logger.info("💾 Fetching SQLite data...")
        sqlite_data = await self.get_sqlite_data()
        
        # Compare data
        channels_ok = await self.compare_channel_configs(firestore_data, sqlite_data)
        posts_ok = await self.compare_sent_post_ids(firestore_data, sqlite_data)
        
        # Final result
        logger.info("\n" + "=" * 60)
        if channels_ok and posts_ok:
            logger.info("🎉 MIGRATION VERIFICATION PASSED!")
            logger.info("✅ All channel configurations migrated correctly")
            logger.info("✅ All sent post IDs migrated correctly")
            logger.info("✅ Ready for production deployment")
        else:
            logger.error("❌ MIGRATION VERIFICATION FAILED!")
            if not channels_ok:
                logger.error("❌ Channel configuration issues found")
            if not posts_ok:
                logger.error("❌ Post ID migration issues found")
            logger.error("⚠️ Do not deploy to production yet!")
        
        logger.info("=" * 60)
        return channels_ok and posts_ok

async def main():
    """Main verification function"""
    verifier = MigrationVerifier()
    success = await verifier.verify_migration()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)