#!/usr/bin/env python3
"""
Simple and reliable server tracking migration for SQLite
Handles SQLite column addition limitations properly
"""

import sqlite3
import os
from datetime import datetime

def add_server_tracking():
    """Add server tracking with SQLite-compatible approach"""
    
    print("Simple Server Tracking Migration")
    print("=" * 35)
    
    db_path = "reddit_bot.db"
    if not os.path.exists(db_path):
        print("ERROR: Database not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(channel_configs)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        print("Current columns:", len(existing_columns))
        
        # Add columns one by one with simple types (no defaults)
        simple_columns = [
            ("guild_id", "TEXT"),
            ("guild_name", "TEXT"), 
            ("channel_name", "TEXT"),
            ("server_owner_id", "TEXT"),
            ("server_owner_name", "TEXT"),
            ("server_member_count", "INTEGER"),
            ("server_created_at", "TEXT"),  # Use TEXT for dates to avoid issues
            ("bot_joined_at", "TEXT"),
            ("added_by_user", "TEXT"),
            ("server_region", "TEXT"),
            ("server_verification_level", "INTEGER"),
            ("total_server_channels", "INTEGER"),
        ]
        
        added_count = 0
        
        for col_name, col_type in simple_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE channel_configs ADD COLUMN {col_name} {col_type}")
                    print(f"✅ Added: {col_name}")
                    added_count += 1
                except Exception as e:
                    print(f"❌ Failed to add {col_name}: {e}")
        
        if added_count == 0:
            print("ℹ️  All columns already exist")
        else:
            print(f"✅ Added {added_count} server tracking columns")
        
        # Create simple server analytics table
        print("\nCreating server analytics table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                guild_name TEXT,
                member_count INTEGER DEFAULT 0,
                total_channels INTEGER DEFAULT 0,
                total_subscriptions INTEGER DEFAULT 0,
                bot_added_at TEXT,
                last_updated TEXT,
                is_active INTEGER DEFAULT 1,
                UNIQUE(guild_id) ON CONFLICT REPLACE
            )
        """)
        print("✅ Created server_analytics table")
        
        # Create performance indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_channel_configs_guild ON channel_configs(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_server_analytics_guild ON server_analytics(guild_id)",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        print("✅ Created indexes")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Server tracking setup complete!")
        print("Your bot will now collect:")
        print("• Discord server names and IDs")
        print("• Member counts and server info") 
        print("• Who added the bot to each server")
        print("• When channels were added")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = add_server_tracking()
    if success:
        print("\n📋 Next: Restart your bot to enable server tracking")
        print("Command: docker-compose restart reddit_feed_bot")
    else:
        print("\n❌ Migration failed")