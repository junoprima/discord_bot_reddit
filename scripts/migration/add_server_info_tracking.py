#!/usr/bin/env python3
"""
Add server information tracking to existing database
This will add columns to track Discord server details
"""

import sqlite3
import os
from datetime import datetime

def add_server_info_columns():
    """Add server tracking columns to channel_configs table"""
    
    print("Adding Server Information Tracking")
    print("=" * 40)
    
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
        
        print("Current columns:", existing_columns)
        print()
        
        # Add new server tracking columns if they don't exist
        new_columns = [
            ("guild_id", "TEXT"),
            ("guild_name", "TEXT"), 
            ("channel_name", "TEXT"),
            ("server_owner_id", "TEXT"),
            ("server_owner_name", "TEXT"),
            ("server_member_count", "INTEGER"),
            ("server_created_at", "DATETIME"),
            ("bot_joined_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
            ("added_by_user", "TEXT"),
            ("server_region", "TEXT"),
            ("server_verification_level", "INTEGER"),
            ("total_server_channels", "INTEGER"),
        ]
        
        added_columns = []
        
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE channel_configs ADD COLUMN {col_name} {col_type}")
                    added_columns.append(col_name)
                    print(f"✅ Added: {col_name}")
                except Exception as e:
                    print(f"❌ Failed to add {col_name}: {e}")
        
        if not added_columns:
            print("ℹ️  All server tracking columns already exist")
        else:
            print(f"\n✅ Added {len(added_columns)} new columns for server tracking")
        
        # Create server analytics table for detailed tracking
        print("\nCreating server analytics table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                guild_name TEXT,
                member_count INTEGER,
                total_channels INTEGER,
                total_subscriptions INTEGER,
                bot_added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                UNIQUE(guild_id) ON CONFLICT REPLACE
            )
        """)
        print("✅ Created server_analytics table")
        
        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_channel_configs_guild ON channel_configs(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_server_analytics_guild ON server_analytics(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_server_analytics_active ON server_analytics(is_active)",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        print("✅ Created performance indexes")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Server information tracking setup complete!")
        print("Your bot will now automatically collect:")
        print("• Server name and ID")
        print("• Server owner information") 
        print("• Member count")
        print("• When bot was added")
        print("• Who added the bot")
        print("• Server creation date")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = add_server_info_columns()
    if success:
        print("\n📋 Next steps:")
        print("1. Update and restart your bot")
        print("2. Server info will be collected automatically")
        print("3. Use server analytics queries to see the data")
    else:
        print("\n❌ Migration failed - check errors above")