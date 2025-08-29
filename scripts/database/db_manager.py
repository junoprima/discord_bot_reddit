#!/usr/bin/env python3
"""
Simple database management script for Reddit Discord Bot
Provides easy commands to query, export, and manage SQLite data.
"""

import sqlite3
import json
import csv
import argparse
from datetime import datetime
import os

class DatabaseManager:
    """Simple database management for Reddit bot"""
    
    def __init__(self, db_path="data/reddit_bot.db"):
        self.db_path = db_path
        
    def connect(self):
        """Create database connection"""
        if not os.path.exists(self.db_path):
            print(f"❌ Database not found: {self.db_path}")
            return None
        return sqlite3.connect(self.db_path)
    
    def show_status(self):
        """Show current bot status"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        print("🤖 Reddit Discord Bot - Database Status")
        print("=" * 50)
        
        # Channel configs
        cursor.execute("SELECT COUNT(*) FROM channel_configs")
        channel_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sent_post_ids")
        post_count = cursor.fetchone()[0]
        
        print(f"📊 Active Channels: {channel_count}")
        print(f"📊 Tracked Post IDs: {post_count}")
        print()
        
        # Show channels
        cursor.execute("""
            SELECT channel_id, subreddit, bot_name, 
                   datetime(last_post_timestamp, 'unixepoch') as last_post_time
            FROM channel_configs 
            ORDER BY last_post_timestamp DESC
        """)
        
        print("📺 Active Channels:")
        for row in cursor.fetchall():
            channel_id, subreddit, bot_name, last_time = row
            print(f"  • {channel_id} → r/{subreddit} ({bot_name})")
            print(f"    Last post: {last_time or 'Never'}")
            print()
        
        conn.close()
    
    def export_channels(self, format="json"):
        """Export channel configurations"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channel_configs")
        
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format.lower() == "json":
            filename = f"channels_export_{timestamp}.json"
            data = [dict(zip(columns, row)) for row in rows]
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        elif format.lower() == "csv":
            filename = f"channels_export_{timestamp}.csv"
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)
        
        print(f"✅ Exported {len(rows)} channels to {filename}")
        conn.close()
    
    def export_posts(self, channel_id=None, limit=100):
        """Export sent post IDs"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        if channel_id:
            cursor.execute("""
                SELECT * FROM sent_post_ids 
                WHERE channel_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (channel_id, limit))
            filename_suffix = f"channel_{channel_id}"
        else:
            cursor.execute("""
                SELECT * FROM sent_post_ids 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            filename_suffix = "all_channels"
        
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"posts_export_{filename_suffix}_{timestamp}.json"
        
        data = [dict(zip(columns, row)) for row in rows]
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"✅ Exported {len(rows)} post IDs to {filename}")
        conn.close()
    
    def cleanup_old_posts(self, days=30, dry_run=True):
        """Clean up old post IDs"""
        conn = self.connect()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Count old posts
        cursor.execute("""
            SELECT COUNT(*) FROM sent_post_ids 
            WHERE created_at < datetime('now', '-{} days')
        """.format(days))
        old_count = cursor.fetchone()[0]
        
        if old_count == 0:
            print(f"✅ No posts older than {days} days found")
            conn.close()
            return
        
        if dry_run:
            print(f"🔍 Found {old_count} posts older than {days} days")
            print("Run with --execute to actually delete them")
        else:
            cursor.execute("""
                DELETE FROM sent_post_ids 
                WHERE created_at < datetime('now', '-{} days')
            """.format(days))
            conn.commit()
            print(f"✅ Deleted {old_count} old posts")
        
        conn.close()
    
    def query_custom(self, sql):
        """Execute custom SQL query"""
        conn = self.connect()
        if not conn:
            return
            
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            
            if sql.strip().upper().startswith('SELECT'):
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                print(f"📊 Query Results ({len(rows)} rows):")
                print("=" * 50)
                
                if rows:
                    # Print headers
                    print(" | ".join(columns))
                    print("-" * 50)
                    
                    # Print rows
                    for row in rows:
                        print(" | ".join(str(cell) for cell in row))
                else:
                    print("No results found")
            else:
                conn.commit()
                print("✅ Query executed successfully")
                
        except Exception as e:
            print(f"❌ Query error: {e}")
        
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Reddit Bot Database Manager")
    parser.add_argument("--db", default="data/reddit_bot.db", help="Database path")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    subparsers.add_parser("status", help="Show database status")
    
    # Export commands
    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("--type", choices=["channels", "posts"], required=True)
    export_parser.add_argument("--format", choices=["json", "csv"], default="json")
    export_parser.add_argument("--channel", help="Channel ID for posts export")
    export_parser.add_argument("--limit", type=int, default=100, help="Limit for posts export")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old posts")
    cleanup_parser.add_argument("--days", type=int, default=30, help="Days to keep")
    cleanup_parser.add_argument("--execute", action="store_true", help="Actually delete (not dry run)")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Execute custom SQL")
    query_parser.add_argument("sql", help="SQL query to execute")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    db_manager = DatabaseManager(args.db)
    
    if args.command == "status":
        db_manager.show_status()
    
    elif args.command == "export":
        if args.type == "channels":
            db_manager.export_channels(args.format)
        elif args.type == "posts":
            db_manager.export_posts(args.channel, args.limit)
    
    elif args.command == "cleanup":
        db_manager.cleanup_old_posts(args.days, not args.execute)
    
    elif args.command == "query":
        db_manager.query_custom(args.sql)

if __name__ == "__main__":
    main()