#!/usr/bin/env python3
"""
Discord Server Analytics Dashboard
Shows detailed analytics about which servers use your bot and how.
"""

import sqlite3
import json
from datetime import datetime, timedelta
import os

class ServerAnalytics:
    """Discord server analytics for Reddit bot"""
    
    def __init__(self, db_path="data/reddit_bot.db"):
        self.db_path = db_path
    
    def connect(self):
        """Create database connection"""
        if not os.path.exists(self.db_path):
            print(f"❌ Database not found: {self.db_path}")
            return None
        return sqlite3.connect(self.db_path)
    
    def server_overview(self):
        """Show overview of all Discord servers using the bot"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("🌐 Discord Server Analytics Overview")
        print("=" * 80)
        
        # Get server statistics
        cursor.execute("""
            SELECT 
                cc.guild_id,
                cc.guild_name,
                COUNT(cc.channel_id) as total_channels,
                COUNT(DISTINCT cc.subreddit) as unique_subreddits,
                MAX(cc.last_post_timestamp) as last_activity,
                cc.added_by_user,
                GROUP_CONCAT(DISTINCT cc.subreddit) as subreddits
            FROM channel_configs cc
            WHERE cc.guild_id IS NOT NULL
            GROUP BY cc.guild_id, cc.guild_name
            ORDER BY total_channels DESC
        """)
        
        servers = cursor.fetchall()
        
        if not servers:
            print("ℹ️  No server data found.")
            print("   Make sure to run: python scripts/migration/add_server_analytics.py")
            conn.close()
            return
        
        total_servers = len(servers)
        total_channels = sum(row[2] for row in servers)
        total_subreddits = len(set(sub for row in servers for sub in row[6].split(',') if row[6]))
        
        print(f"📊 Total Servers: {total_servers}")
        print(f"📊 Total Active Channels: {total_channels}")
        print(f"📊 Unique Subreddits: {total_subreddits}")
        print(f"📊 Avg Channels per Server: {total_channels/total_servers:.1f}")
        print()
        
        print("🏆 Server Details:")
        print("-" * 80)
        print(f"{'Rank':<4} {'Server Name':<25} {'Channels':<8} {'Subreddits':<10} {'Last Activity'}")
        print("-" * 80)
        
        for i, (guild_id, guild_name, channels, unique_subs, last_activity, added_by, subreddits) in enumerate(servers, 1):
            # Format last activity
            if last_activity:
                last_time = datetime.fromtimestamp(last_activity).strftime("%Y-%m-%d %H:%M")
            else:
                last_time = "Never"
            
            server_name = (guild_name or "Unknown Server")[:24]
            
            print(f"{i:<4} {server_name:<25} {channels:<8} {unique_subs:<10} {last_time}")
            
            # Show subreddits for this server
            if subreddits:
                sub_list = ", ".join(f"r/{sub}" for sub in subreddits.split(','))
                print(f"     └─ {sub_list}")
            print()
        
        conn.close()
    
    def server_details(self, guild_id=None):
        """Show detailed information about specific server(s)"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        if guild_id:
            print(f"🏰 Server Details: {guild_id}")
            where_clause = "WHERE cc.guild_id = ?"
            params = (guild_id,)
        else:
            print("🏰 All Server Details")
            where_clause = ""
            params = ()
        
        print("=" * 100)
        
        cursor.execute(f"""
            SELECT 
                cc.guild_id,
                cc.guild_name,
                cc.channel_id,
                cc.channel_name,
                cc.subreddit,
                cc.bot_name,
                cc.added_by_user,
                cc.last_post_timestamp,
                datetime(cc.last_post_timestamp, 'unixepoch') as last_post_time,
                cc.webhook_url
            FROM channel_configs cc
            {where_clause}
            ORDER BY cc.guild_name, cc.channel_name
        """, params)
        
        channels = cursor.fetchall()
        
        current_server = None
        for row in channels:
            guild_id, guild_name, channel_id, channel_name, subreddit, bot_name, added_by, timestamp, last_post, webhook = row
            
            if guild_name != current_server:
                current_server = guild_name
                print(f"\n🏰 Server: {guild_name or 'Unknown Server'} (ID: {guild_id})")
                print("-" * 60)
            
            print(f"  📺 #{channel_name or 'unknown-channel'} ({channel_id})")
            print(f"      └─ Subreddit: r/{subreddit}")
            print(f"      └─ Bot Name: {bot_name}")
            print(f"      └─ Added by: {added_by or 'Unknown'}")
            print(f"      └─ Last Post: {last_post or 'Never'}")
            print(f"      └─ Webhook: {'✅ Active' if webhook else '❌ Missing'}")
            print()
        
        conn.close()
    
    def usage_statistics(self, days=7):
        """Show usage statistics for the past N days"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print(f"📈 Usage Statistics (Last {days} days)")
        print("=" * 60)
        
        # Get post counts per server
        cursor.execute("""
            SELECT 
                cc.guild_name,
                COUNT(sp.post_id) as posts_sent,
                COUNT(DISTINCT sp.channel_id) as active_channels
            FROM sent_post_ids sp
            JOIN channel_configs cc ON sp.channel_id = cc.channel_id
            WHERE sp.created_at >= datetime('now', '-{} days')
            GROUP BY cc.guild_id, cc.guild_name
            ORDER BY posts_sent DESC
        """.format(days))
        
        stats = cursor.fetchall()
        
        if not stats:
            print("ℹ️  No recent activity data found")
            conn.close()
            return
        
        total_posts = sum(row[1] for row in stats)
        total_active_channels = sum(row[2] for row in stats)
        
        print(f"📊 Total Posts Sent: {total_posts}")
        print(f"📊 Active Channels: {total_active_channels}")
        print()
        
        print("🏆 Most Active Servers:")
        print(f"{'Server Name':<30} {'Posts':<8} {'Channels':<10}")
        print("-" * 50)
        
        for guild_name, posts, channels in stats[:10]:
            server_name = (guild_name or "Unknown Server")[:29]
            print(f"{server_name:<30} {posts:<8} {channels:<10}")
        
        conn.close()
    
    def subreddit_popularity(self):
        """Show most popular subreddits across all servers"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("📈 Subreddit Popularity Across All Servers")
        print("=" * 70)
        
        cursor.execute("""
            SELECT 
                cc.subreddit,
                COUNT(cc.channel_id) as total_channels,
                COUNT(DISTINCT cc.guild_id) as total_servers,
                GROUP_CONCAT(DISTINCT cc.guild_name) as server_names
            FROM channel_configs cc
            WHERE cc.guild_id IS NOT NULL
            GROUP BY cc.subreddit
            ORDER BY total_channels DESC
        """)
        
        subreddits = cursor.fetchall()
        
        print(f"{'Subreddit':<25} {'Channels':<8} {'Servers':<8} {'Server Names'}")
        print("-" * 70)
        
        for subreddit, channels, servers, server_names in subreddits:
            # Truncate server names if too long
            names = server_names[:40] + "..." if len(server_names) > 40 else server_names
            print(f"r/{subreddit:<23} {channels:<8} {servers:<8} {names}")
        
        conn.close()
    
    def export_server_analytics(self, filename=None):
        """Export comprehensive server analytics to JSON"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Get comprehensive data
        cursor.execute("""
            SELECT 
                cc.guild_id, cc.guild_name, cc.channel_id, cc.channel_name,
                cc.subreddit, cc.bot_name, cc.added_by_user,
                cc.last_post_timestamp,
                datetime(cc.last_post_timestamp, 'unixepoch') as last_post_time,
                COUNT(sp.post_id) as total_posts_sent
            FROM channel_configs cc
            LEFT JOIN sent_post_ids sp ON cc.channel_id = sp.channel_id
            WHERE cc.guild_id IS NOT NULL
            GROUP BY cc.guild_id, cc.guild_name, cc.channel_id
            ORDER BY cc.guild_name, cc.channel_name
        """)
        
        channels = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        # Structure the data
        analytics = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_channels": len(channels),
                "total_servers": len(set(row[0] for row in channels)),
                "total_posts_sent": sum(row[9] for row in channels),
            },
            "servers": {},
            "subreddit_stats": {}
        }
        
        # Group by server
        for row in channels:
            data = dict(zip(columns, row))
            guild_id = data['guild_id']
            
            if guild_id not in analytics["servers"]:
                analytics["servers"][guild_id] = {
                    "guild_name": data['guild_name'],
                    "channels": [],
                    "total_subscriptions": 0,
                    "total_posts": 0,
                    "subreddits": set()
                }
            
            channel_info = {
                "channel_id": data['channel_id'],
                "channel_name": data['channel_name'],
                "subreddit": data['subreddit'],
                "bot_name": data['bot_name'],
                "added_by": data['added_by_user'],
                "last_post": data['last_post_time'],
                "posts_sent": data['total_posts_sent'] or 0
            }
            
            analytics["servers"][guild_id]["channels"].append(channel_info)
            analytics["servers"][guild_id]["total_subscriptions"] += 1
            analytics["servers"][guild_id]["total_posts"] += channel_info["posts_sent"]
            analytics["servers"][guild_id]["subreddits"].add(data['subreddit'])
        
        # Convert sets to lists for JSON
        for server_id in analytics["servers"]:
            analytics["servers"][server_id]["subreddits"] = list(analytics["servers"][server_id]["subreddits"])
            analytics["servers"][server_id]["unique_subreddits"] = len(analytics["servers"][server_id]["subreddits"])
        
        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"server_analytics_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(analytics, f, indent=2, default=str)
        
        print(f"✅ Server analytics exported to {filename}")
        print(f"📊 Exported data for {analytics['summary']['total_servers']} servers")
        print(f"📊 Total channels: {analytics['summary']['total_channels']}")
        print(f"📊 Total posts sent: {analytics['summary']['total_posts_sent']}")
        
        conn.close()

def main():
    """Main analytics dashboard"""
    analytics = ServerAnalytics()
    
    while True:
        print("\n🤖 Discord Server Analytics Dashboard")
        print("=" * 50)
        print("1. Server Overview")
        print("2. Server Details (All)")
        print("3. Usage Statistics (7 days)")
        print("4. Subreddit Popularity")
        print("5. Export Server Analytics")
        print("6. Exit")
        
        try:
            choice = input("\nSelect option (1-6): ").strip()
            
            if choice == "1":
                analytics.server_overview()
            elif choice == "2":
                analytics.server_details()
            elif choice == "3":
                analytics.usage_statistics()
            elif choice == "4":
                analytics.subreddit_popularity()
            elif choice == "5":
                analytics.export_server_analytics()
            elif choice == "6":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid option. Please choose 1-6.")
                
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()