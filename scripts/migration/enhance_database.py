#!/usr/bin/env python3
"""
Database enhancement script to add Discord server tracking
Adds guild_id, guild_name, and channel_name to track which servers use the bot.
"""

import sqlite3
import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger(__name__)

async def enhance_database():
    """Add server tracking columns to existing database"""
    db_path = "data/reddit_bot.db"
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("🔧 Enhancing database schema...")
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(channel_configs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add new columns if they don't exist
        new_columns = [
            ("guild_id", "TEXT"),
            ("guild_name", "TEXT"),
            ("channel_name", "TEXT"),
            ("added_by_user", "TEXT"),
            ("usage_count", "INTEGER DEFAULT 0"),
            ("last_activity", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE channel_configs ADD COLUMN {col_name} {col_type}")
                logger.info(f"✅ Added column: {col_name}")
            else:
                logger.info(f"ℹ️  Column already exists: {col_name}")
        
        # Create server statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_stats (
                guild_id TEXT PRIMARY KEY,
                guild_name TEXT,
                channel_count INTEGER DEFAULT 0,
                total_posts_sent INTEGER DEFAULT 0,
                first_joined DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        logger.info("✅ Created server_stats table")
        
        # Create usage analytics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                subreddit TEXT,
                post_count INTEGER DEFAULT 1,
                date DATE DEFAULT (date('now')),
                UNIQUE(guild_id, channel_id, subreddit, date) ON CONFLICT REPLACE
            )
        """)
        logger.info("✅ Created usage_analytics table")
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_channel_guild ON channel_configs(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_analytics_date ON usage_analytics(date)",
            "CREATE INDEX IF NOT EXISTS idx_analytics_guild ON usage_analytics(guild_id)",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        logger.info("✅ Created performance indexes")
        
        conn.commit()
        conn.close()
        
        logger.info("🎉 Database enhancement completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhancement failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(enhance_database())
    if success:
        print("\n📊 Your database now supports:")
        print("  • Discord server tracking (guild_id, guild_name)")
        print("  • Channel names and user attribution")
        print("  • Usage statistics and analytics")
        print("  • Server-level metrics")
        print("\nNext: Update your bot to collect this data!")
    else:
        print("❌ Enhancement failed. Check the error messages above.")