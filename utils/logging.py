import os
import logging
from logging.handlers import RotatingFileHandler
from config.settings import get_settings

def setup_logging():
    """Setup logging configuration with proper formatting and rotation"""
    settings = get_settings()
    
    # Ensure logs directory exists
    log_dir = os.path.dirname(settings.log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        handlers=[
            RotatingFileHandler(
                settings.log_file,
                maxBytes=settings.log_max_bytes,
                backupCount=settings.log_backup_count
            ),
            logging.StreamHandler()
        ],
    )
    
    # Set specific loggers to appropriate levels
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('asyncpraw').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully")