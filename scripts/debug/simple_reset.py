#!/usr/bin/env python3
"""
Simple script to reset last 3 posts for all channels
No complex dependencies - just works!
"""

import sqlite3
import os
from datetime import datetime, timedelta

def reset_last_posts_for_all_channels():
    """Reset last 3 posts for all channels - simple and safe"""
    
    print("=== Reset Last 3 Posts for All Channels ===")
    print()
    
    # Check if database exists
    db_path = "reddit_bot.db"
    if not os.path.exists(db_path):
        print("ERROR: Database file 'reddit_bot.db' not found!")
        print("Make sure you're in the bot directory.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all channels
        print("1. Getting all channels...")
        cursor.execute("""
            SELECT channel_id, subreddit, last_post_id, last_post_timestamp,
                   datetime(last_post_timestamp, 'unixepoch') as last_post_time
            FROM channel_configs
        """)
        
        channels = cursor.fetchall()
        print(f"   Found {len(channels)} channels")
        print()
        
        # Show current status
        print("2. Current status:")
        for channel_id, subreddit, last_post_id, timestamp, last_time in channels:
            print(f"   r/{subreddit} (Channel: {channel_id})")
            print(f"      Last post: {last_post_id}")
            print(f"      Last time: {last_time}")
        print()
        
        # Calculate reset time (go back 3 days to catch last 3 posts)
        print("3. Calculating reset timestamps...")
        reset_hours = 72  # 3 days back should catch last 3 posts for most subreddits
        
        updated_count = 0
        
        for channel_id, subreddit, last_post_id, timestamp, last_time in channels:
            if timestamp:
                # Go back 72 hours from current timestamp
                current_timestamp = float(timestamp)
                new_timestamp = current_timestamp - (reset_hours * 3600)
                
                # Update database
                cursor.execute("""
                    UPDATE channel_configs 
                    SET last_post_timestamp = ?, last_post_id = NULL
                    WHERE channel_id = ?
                """, (new_timestamp, channel_id))
                
                old_time = datetime.fromtimestamp(current_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                new_time = datetime.fromtimestamp(new_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"   r/{subreddit}:")
                print(f"      Reset from: {old_time}")
                print(f"      Reset to:   {new_time}")
                print(f"      Will reprocess ~3 days of posts")
                
                updated_count += 1
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print()
        print("4. Reset completed!")
        print(f"   Updated {updated_count} channels")
        print("   Bot will reprocess recent posts on next run")
        print()
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def clean_recent_sent_posts():
    """Remove recent sent posts to allow reprocessing"""
    
    print("=== Cleaning Recent Sent Posts ===")
    print()
    
    try:
        conn = sqlite3.connect("reddit_bot.db")
        cursor = conn.cursor()
        
        # Count current sent posts
        cursor.execute("SELECT COUNT(*) FROM sent_post_ids")
        total_posts = cursor.fetchone()[0]
        
        print(f"1. Current sent posts in database: {total_posts}")
        
        # Remove posts from last 3 days to allow reprocessing
        cutoff_time = datetime.now() - timedelta(days=3)
        cutoff_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("SELECT COUNT(*) FROM sent_post_ids WHERE created_at >= ?", (cutoff_str,))
        recent_posts = cursor.fetchone()[0]
        
        print(f"2. Posts from last 3 days: {recent_posts}")
        print(f"3. These will be removed to allow reprocessing...")
        
        # Remove recent posts
        cursor.execute("DELETE FROM sent_post_ids WHERE created_at >= ?", (cutoff_str,))
        removed_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"4. Removed {removed_count} recent post records")
        print("   Bot can now reprocess these posts")
        print()
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    print("Discord Bot - Reset Last 3 Posts Tool")
    print("=====================================")
    print()
    
    # Step 1: Reset timestamps
    success1 = reset_last_posts_for_all_channels()
    
    if success1:
        print()
        # Step 2: Clean sent posts
        success2 = clean_recent_sent_posts()
        
        if success2:
            print("=== SUCCESS! All Done! ===")
            print()
            print("Next steps:")
            print("1. Start bot: docker-compose up -d")
            print("2. Watch logs: docker logs -f reddit_feed_bot")
            print("3. Check Discord for reprocessed posts")
            print()
            print("The bot will:")
            print("- Reprocess last ~3 posts per channel")
            print("- Auto-recreate any broken webhooks")
            print("- Skip true duplicates")
            print("=====================================")
        else:
            print("ERROR in step 2")
    else:
        print("ERROR in step 1")