#!/usr/bin/env python3
"""
Statistics Dashboard for Reddit Discord Bot
Shows server usage, channel statistics, and analytics.
"""

import sqlite3
import json
from datetime import datetime, timedelta
import os

class BotStatistics:
    """Generate statistics for Reddit Discord Bot"""
    
    def __init__(self, db_path="data/reddit_bot.db"):
        self.db_path = db_path
    
    def connect(self):
        """Create database connection"""
        if not os.path.exists(self.db_path):
            print(f"❌ Database not found: {self.db_path}")
            return None
        return sqlite3.connect(self.db_path)
    
    def server_overview(self):
        """Show server-level statistics"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("🌐 Discord Server Overview")
        print("=" * 60)
        
        # Get server stats
        cursor.execute("""
            SELECT 
                guild_id,
                guild_name,
                COUNT(*) as channel_count,
                GROUP_CONCAT(DISTINCT subreddit) as subreddits,
                MAX(last_activity) as last_activity
            FROM channel_configs 
            WHERE guild_id IS NOT NULL
            GROUP BY guild_id, guild_name
            ORDER BY channel_count DESC
        """)
        
        servers = cursor.fetchall()
        
        if not servers:
            print("ℹ️  No server data found. Run enhance_database.py first.")
            conn.close()
            return
        
        total_servers = len(servers)
        total_channels = sum(row[2] for row in servers)
        
        print(f"📊 Total Servers: {total_servers}")
        print(f"📊 Total Channels: {total_channels}")
        print(f"📊 Avg Channels per Server: {total_channels/total_servers:.1f}")
        print()
        
        print("🏆 Top Servers by Channel Count:")
        print("-" * 60)
        
        for i, (guild_id, guild_name, channel_count, subreddits, last_activity) in enumerate(servers[:10], 1):
            subreddit_list = subreddits.split(',') if subreddits else []
            unique_subreddits = len(set(subreddit_list))
            
            print(f"{i:2d}. {guild_name or 'Unknown Server'}")
            print(f"    Server ID: {guild_id}")
            print(f"    Channels: {channel_count}")
            print(f"    Unique Subreddits: {unique_subreddits}")
            print(f"    Last Activity: {last_activity or 'Unknown'}")
            if subreddits:
                print(f"    Subreddits: {', '.join(set(subreddit_list))}")
            print()
        
        conn.close()
    
    def channel_details(self):
        """Show detailed channel information"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("📺 Channel Details")
        print("=" * 80)
        
        cursor.execute("""
            SELECT 
                channel_id,
                guild_name,
                channel_name,
                subreddit,
                bot_name,
                added_by_user,
                last_post_timestamp,
                datetime(last_post_timestamp, 'unixepoch') as last_post_time
            FROM channel_configs
            ORDER BY guild_name, channel_name
        """)
        
        channels = cursor.fetchall()
        
        current_server = None
        for row in channels:
            channel_id, guild_name, channel_name, subreddit, bot_name, added_by, timestamp, last_post = row
            
            if guild_name != current_server:
                current_server = guild_name
                print(f"\n🏰 Server: {guild_name or 'Unknown Server'}")
                print("-" * 40)
            
            print(f"  📺 #{channel_name or 'unknown-channel'} ({channel_id})")
            print(f"      Subreddit: r/{subreddit}")
            print(f"      Bot Name: {bot_name}")
            print(f"      Added by: {added_by or 'Unknown'}")
            print(f"      Last Post: {last_post or 'Never'}")
            print()
        
        conn.close()
    
    def subreddit_popularity(self):
        """Show most popular subreddits"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("📈 Subreddit Popularity")
        print("=" * 50)
        
        cursor.execute("""
            SELECT 
                subreddit,
                COUNT(*) as channel_count,
                COUNT(DISTINCT guild_id) as server_count
            FROM channel_configs
            GROUP BY subreddit
            ORDER BY channel_count DESC
        """)
        
        subreddits = cursor.fetchall()
        
        print(f"{'Rank':<4} {'Subreddit':<25} {'Channels':<8} {'Servers':<8}")
        print("-" * 50)
        
        for i, (subreddit, channels, servers) in enumerate(subreddits, 1):
            print(f"{i:<4} r/{subreddit:<23} {channels:<8} {servers:<8}")
        
        conn.close()
    
    def export_statistics(self, filename=None):
        """Export statistics to JSON"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Get all data
        cursor.execute("""
            SELECT 
                guild_id, guild_name, channel_id, channel_name,
                subreddit, bot_name, added_by_user,
                last_post_timestamp,
                datetime(last_post_timestamp, 'unixepoch') as last_post_time
            FROM channel_configs
            ORDER BY guild_name, channel_name
        """)
        
        channels = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        # Convert to structured data
        stats = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_channels": len(channels),
                "total_servers": len(set(row[0] for row in channels if row[0])),
            },
            "servers": {},
            "subreddits": {}
        }
        
        # Group by server
        for row in channels:
            data = dict(zip(columns, row))
            guild_id = data['guild_id']
            
            if guild_id not in stats["servers"]:
                stats["servers"][guild_id] = {
                    "guild_name": data['guild_name'],
                    "channels": [],
                    "channel_count": 0,
                    "subreddits": set()
                }
            
            stats["servers"][guild_id]["channels"].append({
                "channel_id": data['channel_id'],
                "channel_name": data['channel_name'],
                "subreddit": data['subreddit'],
                "bot_name": data['bot_name'],
                "added_by": data['added_by_user'],
                "last_post": data['last_post_time']
            })
            
            stats["servers"][guild_id]["channel_count"] += 1
            stats["servers"][guild_id]["subreddits"].add(data['subreddit'])
        
        # Convert sets to lists for JSON serialization
        for server_id in stats["servers"]:
            stats["servers"][server_id]["subreddits"] = list(stats["servers"][server_id]["subreddits"])
        
        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bot_statistics_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        
        print(f"✅ Statistics exported to {filename}")
        conn.close()

def main():
    """Main dashboard function"""
    stats = BotStatistics()
    
    while True:
        print("\n🤖 Reddit Discord Bot - Statistics Dashboard")
        print("=" * 50)
        print("1. Server Overview")
        print("2. Channel Details") 
        print("3. Subreddit Popularity")
        print("4. Export Statistics (JSON)")
        print("5. Exit")
        
        try:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == "1":
                stats.server_overview()
            elif choice == "2":
                stats.channel_details()
            elif choice == "3":
                stats.subreddit_popularity()
            elif choice == "4":
                stats.export_statistics()
            elif choice == "5":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid option. Please choose 1-5.")
                
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()