#!/usr/bin/env python3
"""
Display current bot settings from both Firestore and SQLite
Shows what channels are configured and their settings.
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
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def show_firestore_settings():
    """Show current Firestore settings (main branch)"""
    print("\n🔥 FIRESTORE SETTINGS (Current Main Branch)")
    print("=" * 60)
    
    try:
        firebase_creds = os.getenv("FIREBASE_CREDENTIALS")
        if not firebase_creds:
            print("❌ FIREBASE_CREDENTIALS not found in .env")
            return
            
        cred = credentials.Certificate(firebase_creds)
        initialize_app(cred)
        firestore_client = firestore.client()
        
        # Get channel configs
        configs = firestore_client.collection("channel_configs").stream()
        channel_count = 0
        
        for config in configs:
            data = config.to_dict()
            channel_id = data.get("channel_id", "unknown")
            subreddit = data.get("subreddit", "unknown")
            bot_name = data.get("bot_name", "N/A")
            last_post_id = data.get("last_post_id", "N/A")
            last_timestamp = data.get("last_post_timestamp", 0)
            
            print(f"📺 Channel: {channel_id}")
            print(f"   └── Subreddit: r/{subreddit}")
            print(f"   └── Bot Name: {bot_name}")
            print(f"   └── Last Post: {last_post_id}")
            print(f"   └── Last Timestamp: {last_timestamp}")
            print()
            channel_count += 1
        
        # Get sent post IDs
        sent_posts = firestore_client.collection("sent_post_ids").stream()
        total_post_ids = 0
        
        for sent_post in sent_posts:
            data = sent_post.to_dict()
            post_ids = data.get("post_ids", [])
            total_post_ids += len(post_ids)
        
        print(f"📊 Summary:")
        print(f"   • {channel_count} Discord channels configured")
        print(f"   • {total_post_ids} total post IDs stored")
        
    except Exception as e:
        print(f"❌ Error reading Firestore: {e}")

async def show_sqlite_settings():
    """Show current SQLite settings (dev branch)"""
    print("\n💾 SQLITE SETTINGS (New Dev Branch)")
    print("=" * 60)
    
    sqlite_path = "data/reddit_bot.db"
    
    try:
        if not os.path.exists(sqlite_path):
            print("ℹ️ SQLite database not found (not migrated yet)")
            print(f"   Expected location: {os.path.abspath(sqlite_path)}")
            return
            
        async with aiosqlite.connect(sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get channel configs
            async with db.execute("SELECT * FROM channel_configs") as cursor:
                rows = await cursor.fetchall()
                
                for row in rows:
                    print(f"📺 Channel: {row['channel_id']}")
                    print(f"   └── Subreddit: r/{row['subreddit']}")
                    print(f"   └── Bot Name: {row['bot_name']}")
                    print(f"   └── Last Post: {row['last_post_id']}")
                    print(f"   └── Last Timestamp: {row['last_post_timestamp']}")
                    print()
            
            # Count post IDs
            async with db.execute("SELECT COUNT(*) as count FROM sent_post_ids") as cursor:
                result = await cursor.fetchone()
                total_post_ids = result['count']
            
            print(f"📊 Summary:")
            print(f"   • {len(rows)} Discord channels configured")
            print(f"   • {total_post_ids} total post IDs stored")
            
    except Exception as e:
        print(f"❌ Error reading SQLite: {e}")

async def show_environment_info():
    """Show environment configuration"""
    print("\n🌍 ENVIRONMENT INFORMATION")
    print("=" * 60)
    
    env_vars = [
        "DISCORD_TOKEN",
        "REDDIT_CLIENT_ID", 
        "REDDIT_CLIENT_SECRET",
        "REDDIT_USER_AGENT",
        "FIREBASE_CREDENTIALS"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if var == "DISCORD_TOKEN" and len(value) > 10:
                display_value = f"{value[:10]}...{value[-4:]}"
            elif var in ["REDDIT_CLIENT_SECRET"] and len(value) > 8:
                display_value = f"{value[:4]}...{value[-4:]}"
            else:
                display_value = "✅ Set"
            print(f"   {var}: {display_value}")
        else:
            print(f"   {var}: ❌ Not set")

async def main():
    """Main function to show all current settings"""
    print("🤖 DISCORD REDDIT BOT - CURRENT SETTINGS")
    print("=" * 60)
    
    # Show environment
    await show_environment_info()
    
    # Show Firestore settings (current production)
    await show_firestore_settings()
    
    # Show SQLite settings (new dev)
    await show_sqlite_settings()
    
    print("\n" + "=" * 60)
    print("💡 Next Steps:")
    print("   1. If SQLite is empty, run: python migrate_firestore_to_sqlite.py")
    print("   2. Verify migration: python verify_migration.py") 
    print("   3. Deploy to production following MIGRATION_PLAN.md")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())