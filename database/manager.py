import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
import aiosqlite
from config.settings import get_settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """SQLite database manager for Reddit bot data storage"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_path = self.settings.database_path
        self._init_lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize database tables if they don't exist"""
        if self._initialized:
            return
            
        async with self._init_lock:
            if self._initialized:
                return
                
            async with aiosqlite.connect(self.db_path) as db:
                await self._create_tables(db)
                await db.commit()
                logger.info("Database initialized successfully")
                
            self._initialized = True
    
    async def _create_tables(self, db: aiosqlite.Connection):
        """Create database tables"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_configs (
                channel_id TEXT PRIMARY KEY,
                subreddit TEXT NOT NULL,
                webhook_url TEXT NOT NULL,
                bot_name TEXT,
                bot_avatar TEXT,
                last_post_id TEXT,
                last_post_timestamp REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sent_post_ids (
                channel_id TEXT,
                post_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (channel_id, post_id)
            )
        """)
        
        # Create index for faster queries
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sent_posts_channel 
            ON sent_post_ids(channel_id, created_at)
        """)
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection with proper error handling"""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db
    
    async def get_channel_config(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel configuration by ID"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT * FROM channel_configs WHERE channel_id = ?", 
                (channel_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_all_channel_configs(self) -> List[Dict[str, Any]]:
        """Get all channel configurations"""
        async with self.get_connection() as db:
            async with db.execute("SELECT * FROM channel_configs") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def update_channel_config(self, channel_id: str, data: Dict[str, Any]):
        """Update or insert channel configuration"""
        async with self.get_connection() as db:
            existing = await self.get_channel_config(channel_id)
            
            if existing:
                # Update existing record
                set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
                query = f"""
                    UPDATE channel_configs 
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP 
                    WHERE channel_id = ?
                """
                values = list(data.values()) + [channel_id]
            else:
                # Insert new record
                data['channel_id'] = channel_id
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])
                query = f"INSERT INTO channel_configs ({columns}) VALUES ({placeholders})"
                values = list(data.values())
            
            await db.execute(query, values)
            await db.commit()
            logger.info(f"Channel config updated for {channel_id}")
    
    async def delete_channel_config(self, channel_id: str):
        """Delete channel configuration and associated sent post IDs"""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM channel_configs WHERE channel_id = ?", (channel_id,))
            await db.execute("DELETE FROM sent_post_ids WHERE channel_id = ?", (channel_id,))
            await db.commit()
            logger.info(f"Channel config deleted for {channel_id}")
    
    async def is_duplicate_post(self, channel_id: str, post_id: str) -> bool:
        """Check if post ID already exists for channel"""
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT 1 FROM sent_post_ids WHERE channel_id = ? AND post_id = ?",
                (channel_id, post_id)
            ) as cursor:
                return await cursor.fetchone() is not None
    
    async def add_sent_post_id(self, channel_id: str, post_id: str):
        """Add post ID to sent posts, maintaining only last N entries per channel"""
        settings = get_settings()
        async with self.get_connection() as db:
            # Insert new post ID
            await db.execute(
                "INSERT OR IGNORE INTO sent_post_ids (channel_id, post_id) VALUES (?, ?)",
                (channel_id, post_id)
            )
            
            # Keep only the last N post IDs per channel
            await db.execute("""
                DELETE FROM sent_post_ids 
                WHERE channel_id = ? AND rowid NOT IN (
                    SELECT rowid FROM sent_post_ids 
                    WHERE channel_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                )
            """, (channel_id, channel_id, settings.max_stored_post_ids))
            
            await db.commit()
            logger.debug(f"Added post {post_id} to sent_post_ids for channel {channel_id}")
    
    async def update_last_post_info(self, channel_id: str, post_id: str, timestamp: float):
        """Update last post ID and timestamp for channel"""
        async with self.get_connection() as db:
            await db.execute("""
                UPDATE channel_configs 
                SET last_post_id = ?, last_post_timestamp = ?, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            """, (post_id, timestamp, channel_id))
            await db.commit()
    
    async def cleanup_old_posts(self, days: int = None):
        """Remove old sent post IDs (cleanup task)"""
        if days is None:
            days = get_settings().cleanup_days
            
        async with self.get_connection() as db:
            await db.execute("""
                DELETE FROM sent_post_ids 
                WHERE created_at < datetime('now', '-{} days')
            """.format(days))
            await db.commit()
            logger.info(f"Cleaned up post IDs older than {days} days")
    
    async def record_server_info(self, guild_data: Dict[str, Any]):
        """Record Discord server information when bot joins"""
        async with self.get_connection() as db:
            await db.execute("""
                INSERT OR REPLACE INTO server_analytics (
                    guild_id, guild_name, member_count, total_channels,
                    bot_added_at, last_updated, is_active
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            """, (
                guild_data['guild_id'],
                guild_data['guild_name'], 
                guild_data.get('member_count', 0),
                guild_data.get('total_channels', 0)
            ))
            await db.commit()
            logger.info(f"Recorded server info for {guild_data['guild_name']} ({guild_data['guild_id']})")
    
    async def update_channel_server_info(self, channel_id: str, server_data: Dict[str, Any]):
        """Update server information for a specific channel"""
        async with self.get_connection() as db:
            await db.execute("""
                UPDATE channel_configs 
                SET guild_id = ?, guild_name = ?, channel_name = ?,
                    server_owner_id = ?, server_owner_name = ?, server_member_count = ?,
                    server_created_at = ?, added_by_user = ?, server_region = ?,
                    server_verification_level = ?, total_server_channels = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            """, (
                server_data.get('guild_id'),
                server_data.get('guild_name'),
                server_data.get('channel_name'),
                server_data.get('server_owner_id'),
                server_data.get('server_owner_name'),
                server_data.get('server_member_count'),
                server_data.get('server_created_at'),
                server_data.get('added_by_user'),
                server_data.get('server_region'),
                server_data.get('server_verification_level'),
                server_data.get('total_server_channels'),
                channel_id
            ))
            await db.commit()
            logger.debug(f"Updated server info for channel {channel_id}")
    
    async def get_server_analytics(self) -> List[Dict[str, Any]]:
        """Get server analytics data"""
        async with self.get_connection() as db:
            cursor = await db.execute("""
                SELECT sa.*, 
                       COUNT(cc.channel_id) as active_subscriptions
                FROM server_analytics sa
                LEFT JOIN channel_configs cc ON sa.guild_id = cc.guild_id
                WHERE sa.is_active = 1
                GROUP BY sa.guild_id
                ORDER BY sa.member_count DESC
            """)
            
            columns = [description[0] for description in cursor.description]
            rows = await cursor.fetchall()
            
            return [dict(zip(columns, row)) for row in rows]