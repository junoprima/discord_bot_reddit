import os
import logging
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    """Application configuration settings"""
    
    # Discord Configuration
    discord_token: str
    
    # Reddit Configuration  
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str
    
    # Database Configuration
    database_path: str = "reddit_bot.db"
    
    # Bot Configuration
    fetch_interval_minutes: int = 1
    max_posts_per_fetch: int = 10
    max_stored_post_ids: int = 100
    cleanup_days: int = 30
    
    # Logging Configuration
    log_level: str = "INFO"
    log_file: str = "logs/reddit_feed_bot.log"
    log_max_bytes: int = 5 * 1024 * 1024  # 5MB
    log_backup_count: int = 3
    
    @classmethod
    def from_env(cls) -> 'Settings':
        """Load settings from environment variables"""
        required_vars = [
            'DISCORD_TOKEN',
            'REDDIT_CLIENT_ID', 
            'REDDIT_CLIENT_SECRET',
            'REDDIT_USER_AGENT'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        return cls(
            discord_token=os.getenv('DISCORD_TOKEN'),
            reddit_client_id=os.getenv('REDDIT_CLIENT_ID'),
            reddit_client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            reddit_user_agent=os.getenv('REDDIT_USER_AGENT'),
            database_path=os.getenv('DATABASE_PATH', 'reddit_bot.db'),
            fetch_interval_minutes=int(os.getenv('FETCH_INTERVAL_MINUTES', '1')),
            max_posts_per_fetch=int(os.getenv('MAX_POSTS_PER_FETCH', '10')),
            max_stored_post_ids=int(os.getenv('MAX_STORED_POST_IDS', '100')),
            cleanup_days=int(os.getenv('CLEANUP_DAYS', '30')),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file=os.getenv('LOG_FILE', 'logs/reddit_feed_bot.log'),
            log_max_bytes=int(os.getenv('LOG_MAX_BYTES', str(5 * 1024 * 1024))),
            log_backup_count=int(os.getenv('LOG_BACKUP_COUNT', '3'))
        )

# Global settings instance
settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get application settings singleton"""
    global settings
    if settings is None:
        settings = Settings.from_env()
    return settings