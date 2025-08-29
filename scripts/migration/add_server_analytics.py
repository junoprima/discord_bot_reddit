#!/usr/bin/env python3
"""
Add comprehensive Discord server analytics to the database
Tracks servers, member counts, activity, and usage patterns.
"""

import sqlite3
import asyncio
import logging
import os
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger(__name__)

async def add_server_analytics():
    """Add server analytics tables and update existing data"""
    db_path = "data/reddit_bot.db"
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("🔧 Adding server analytics tables...")
        
        # Enhanced server tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discord_servers (
                guild_id TEXT PRIMARY KEY,
                guild_name TEXT NOT NULL,
                member_count INTEGER DEFAULT 0,
                owner_id TEXT,
                owner_name TEXT,
                server_created_at DATETIME,
                bot_joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                server_region TEXT,
                verification_level INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_channels INTEGER DEFAULT 0,
                total_subscriptions INTEGER DEFAULT 0,
                total_posts_sent INTEGER DEFAULT 0
            )
        """)
        logger.info("✅ Created discord_servers table")
        
        # Daily analytics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE DEFAULT (date('now')),
                guild_id TEXT,
                channel_id TEXT,
                subreddit TEXT,
                posts_sent INTEGER DEFAULT 0,
                webhook_calls INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                UNIQUE(date, guild_id, channel_id, subreddit) ON CONFLICT REPLACE,
                FOREIGN KEY (guild_id) REFERENCES discord_servers(guild_id)
            )
        """)
        logger.info("✅ Created daily_analytics table")
        
        # Bot usage events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                guild_id TEXT,
                channel_id TEXT,
                user_id TEXT,
                user_name TEXT,
                event_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES discord_servers(guild_id)
            )
        """)
        logger.info("✅ Created bot_events table")
        
        # Server growth tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_growth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                date DATE DEFAULT (date('now')),
                member_count INTEGER,
                channel_count INTEGER,
                active_subscriptions INTEGER,
                UNIQUE(guild_id, date) ON CONFLICT REPLACE,
                FOREIGN KEY (guild_id) REFERENCES discord_servers(guild_id)
            )
        """)
        logger.info("✅ Created server_growth table")
        
        # Performance indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_daily_analytics_date ON daily_analytics(date)",
            "CREATE INDEX IF NOT EXISTS idx_daily_analytics_guild ON daily_analytics(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_bot_events_type ON bot_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_bot_events_guild ON bot_events(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_server_growth_date ON server_growth(date)",
            "CREATE INDEX IF NOT EXISTS idx_servers_active ON discord_servers(is_active)",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        logger.info("✅ Created performance indexes")
        
        # Add analytics columns to existing channel_configs if not exists
        cursor.execute("PRAGMA table_info(channel_configs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        analytics_columns = [
            ("total_posts_sent", "INTEGER DEFAULT 0"),
            ("last_successful_post", "DATETIME"),
            ("error_count", "INTEGER DEFAULT 0"),
            ("webhook_calls", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_type in analytics_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE channel_configs ADD COLUMN {col_name} {col_type}")
                logger.info(f"✅ Added analytics column: {col_name}")
        
        conn.commit()
        conn.close()
        
        logger.info("🎉 Server analytics enhancement completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhancement failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(add_server_analytics())
    if success:
        print("\n📊 Enhanced database with server analytics:")
        print("  • Discord server tracking (member count, owner, etc.)")
        print("  • Daily analytics per server/channel")
        print("  • Bot usage events logging")
        print("  • Server growth metrics")
        print("  • Performance tracking")
        print("\nNext: Update bot code to collect this data!")
    else:
        print("❌ Enhancement failed. Check the error messages above.")