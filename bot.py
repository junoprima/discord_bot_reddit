import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any
import discord
from discord.ext import commands, tasks
from discord import app_commands

# Import our modular components
from config.settings import get_settings
from utils.logging import setup_logging
from database.manager import DatabaseManager
from services.reddit import RedditService
from services.discord_utils import DiscordWebhookService, EmbedBuilder

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)

class RedditBot(commands.Bot):
    """Main Reddit Discord Bot class with cogs-based architecture"""
    
    def __init__(self):
        self.settings = get_settings()
        self.startup_time = datetime.now()
        
        # Initialize Discord bot
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)  # Prefix for text commands (if any)
        
        # Initialize services
        self.db_manager = DatabaseManager()
        self.reddit_service = RedditService()
        self.webhook_service = DiscordWebhookService(self.db_manager, self.reddit_service)
        
        # Cache for channel configs
        self.channel_configs: Dict[str, Dict[str, Any]] = {}
    
    @property
    def uptime(self):
        """Get bot uptime as a formatted string"""
        delta = datetime.now() - self.startup_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"
    
    async def setup_hook(self):
        """Setup hook called when bot is ready"""
        logger.info("Setting up bot services...")
        
        # Initialize all services
        await self.db_manager.initialize()
        await self.reddit_service.initialize()
        await self.webhook_service.initialize()
        
        # Load channel configs into cache
        await self.load_channel_configs()
        
        # Load all cogs
        await self.load_cogs()
        
        # Start periodic tasks
        self.reddit_fetch_task.start()
        
        logger.info("Bot setup completed")
    
    async def load_cogs(self):
        """Load all cogs from the cogs directory"""
        cogs_dir = "cogs"
        cog_files = [
            "reddit_commands",
            "bot_management", 
            "admin_commands"
        ]
        
        loaded_cogs = []
        failed_cogs = []
        
        for cog_file in cog_files:
            try:
                await self.load_extension(f"{cogs_dir}.{cog_file}")
                loaded_cogs.append(cog_file)
                logger.info(f"✅ Loaded cog: {cog_file}")
            except Exception as e:
                failed_cogs.append(f"{cog_file}: {e}")
                logger.error(f"❌ Failed to load cog {cog_file}: {e}")
        
        logger.info(f"Cogs loaded: {len(loaded_cogs)} success, {len(failed_cogs)} failed")
        
        if failed_cogs:
            logger.warning(f"Failed cogs: {failed_cogs}")
    
    async def load_channel_configs(self):
        """Load all channel configurations into memory cache"""
        try:
            configs = await self.db_manager.get_all_channel_configs()
            self.channel_configs = {config["channel_id"]: config for config in configs}
            logger.info(f"Loaded {len(configs)} channel configurations")
        except Exception as e:
            logger.error(f"Failed to load channel configurations: {e}")
    
    async def update_channel_config_cache(self, channel_id: str, data: Dict[str, Any]):
        """Update both database and cache with new config"""
        await self.db_manager.update_channel_config(channel_id, data)
        
        # Update cache
        if channel_id in self.channel_configs:
            self.channel_configs[channel_id].update(data)
        else:
            config = await self.db_manager.get_channel_config(channel_id)
            if config:
                self.channel_configs[channel_id] = config
    
    async def _update_server_analytics(self):
        """Update server analytics for all guilds bot is in"""
        try:
            for guild in self.guilds:
                await self._record_server_info(guild)
        except Exception as e:
            logger.error(f"Error updating server analytics: {e}")
    
    async def _record_server_info(self, guild):
        """Record Discord server information to database"""
        try:
            # Get comprehensive server data
            server_data = {
                'guild_id': str(guild.id),
                'guild_name': guild.name,
                'member_count': guild.member_count,
                'server_owner_id': str(guild.owner_id) if guild.owner_id else None,
                'server_owner_name': guild.owner.name if guild.owner else None,
                'server_created_at': guild.created_at.isoformat(),
                'server_region': str(guild.preferred_locale) if guild.preferred_locale else None,
                'server_verification_level': guild.verification_level.value,
                'total_server_channels': len(guild.channels),
            }
            
            # Count current subscriptions in this server
            subscriptions = sum(1 for config in self.channel_configs.values() 
                              if config.get('guild_id') == str(guild.id))
            
            # Record to server analytics table
            analytics_data = {
                'guild_id': server_data['guild_id'],
                'guild_name': server_data['guild_name'],
                'member_count': server_data['member_count'],
                'total_channels': server_data['total_server_channels']
            }
            
            await self.db_manager.record_server_info(analytics_data)
            
            # Update any existing channel configs with server info
            for channel_id, config in self.channel_configs.items():
                if config.get('guild_id') == str(guild.id):
                    # Get channel details
                    channel = guild.get_channel(int(channel_id))
                    if channel:
                        server_data['channel_name'] = channel.name
                        await self.db_manager.update_channel_server_info(channel_id, server_data)
            
            logger.info(f"📊 Recorded server info: {guild.name} ({guild.member_count} members, {len(guild.channels)} channels)")
            
        except Exception as e:
            logger.error(f"Error recording server info for {guild.name}: {e}")
    
    async def _update_server_record(self, server_data):
        """Update server record in database - deprecated, using record_server_info instead"""
        logger.debug(f"Server record updated: {server_data.get('guild_name', 'Unknown')}")
    
    async def on_guild_join(self, guild):
        """Called when bot joins a new server"""
        logger.info(f"🎉 Bot joined new server: {guild.name} ({guild.id}) - {guild.member_count} members")
        await self._record_server_info(guild)
        await self._log_bot_event("guild_join", guild.id, data=f"Server: {guild.name}, Members: {guild.member_count}")
    
    async def on_guild_remove(self, guild):
        """Called when bot leaves a server"""
        logger.info(f"👋 Bot removed from server: {guild.name} ({guild.id})")
        await self._log_bot_event("guild_leave", guild.id, data=f"Server: {guild.name}")
    
    async def _log_bot_event(self, event_type, guild_id=None, channel_id=None, user_id=None, user_name=None, data=None):
        """Log bot usage events"""
        try:
            # This would be implemented in DatabaseManager
            logger.info(f"Bot event: {event_type} in server {guild_id}")
        except Exception as e:
            logger.error(f"Error logging bot event: {e}")
    
    async def on_ready(self):
        """Called when bot is ready"""
        await self.tree.sync()
        
        # Update server analytics
        await self._update_server_analytics()
        
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Monitoring {len(self.channel_configs)} channels")
        logger.info(f"Active in {len(self.guilds)} Discord servers")
    
    async def close(self):
        """Cleanup when bot shuts down"""
        logger.info("Shutting down bot...")
        
        # Stop tasks
        if hasattr(self, 'reddit_fetch_task'):
            self.reddit_fetch_task.cancel()
        
        # Cleanup services
        await self.reddit_service.cleanup()
        await self.webhook_service.cleanup()
        
        await super().close()
    
    @tasks.loop(minutes=1)  # Will be configurable via settings
    async def reddit_fetch_task(self):
        """Periodic task to fetch Reddit posts and send to Discord"""
        if not self.channel_configs:
            return
        
        logger.info(f"Starting fetch task for {len(self.channel_configs)} channels")
        
        for channel_id, config in self.channel_configs.items():
            try:
                await self.process_channel_posts(channel_id, config)
            except Exception as e:
                logger.error(f"Error processing channel {channel_id}: {e}")
    
    async def process_channel_posts(self, channel_id: str, config: Dict[str, Any]):
        """Process new posts for a specific channel"""
        subreddit = config.get("subreddit")
        webhook_url = config.get("webhook_url")
        last_post_timestamp = float(config.get("last_post_timestamp", 0))
        
        if not subreddit or not webhook_url:
            logger.warning(f"Channel {channel_id} missing subreddit or webhook URL")
            return
        
        # Fetch new posts
        new_posts = await self.reddit_service.fetch_reddit_posts(subreddit, last_post_timestamp)
        
        if not new_posts:
            return
        
        logger.info(f"Processing {len(new_posts)} new posts for r/{subreddit} in channel {channel_id}")
        
        for post in new_posts:
            try:
                # Skip duplicates
                if await self.db_manager.is_duplicate_post(channel_id, post.id):
                    logger.debug(f"Post {post.id} already processed, skipping")
                    continue
                
                # Extract media URLs
                media_urls = await self.reddit_service.extract_media_urls(post)
                
                # Create embeds
                embeds = await EmbedBuilder.create_post_embeds(
                    post, subreddit, media_urls, self.reddit_service
                )
                
                # Send via webhook with auto-recreation on 404
                webhook_success = await self.webhook_service.send_webhook_message(
                    webhook_url=webhook_url,
                    embeds=embeds,
                    username=config.get("bot_name", f"r/{subreddit}"),
                    avatar_url=config.get("bot_avatar"),
                    post_link=f"https://www.reddit.com{post.permalink}"
                )
                
                # If webhook failed with 404, recreate it and try again
                if not webhook_success:
                    logger.warning(f"Webhook failed for channel {channel_id}, attempting recreation...")
                    new_webhook_url = await self.webhook_service.validate_and_recreate_webhook(
                        channel_id, self, config
                    )
                    
                    if new_webhook_url:
                        # Update cache with new webhook URL
                        self.channel_configs[channel_id]["webhook_url"] = new_webhook_url
                        
                        # Retry sending with new webhook
                        webhook_success = await self.webhook_service.send_webhook_message(
                            webhook_url=new_webhook_url,
                            embeds=embeds,
                            username=config.get("bot_name", f"r/{subreddit}"),
                            avatar_url=config.get("bot_avatar"),
                            post_link=f"https://www.reddit.com{post.permalink}"
                        )
                        
                        if webhook_success:
                            logger.info(f"Successfully sent message after webhook recreation for channel {channel_id}")
                        else:
                            logger.error(f"Failed to send message even after webhook recreation for channel {channel_id}")
                    else:
                        logger.error(f"Could not recreate webhook for channel {channel_id}")
                        continue  # Skip this post if webhook can't be recreated
                
                # Update tracking
                await self.db_manager.add_sent_post_id(channel_id, post.id)
                await self.db_manager.update_last_post_info(channel_id, post.id, post.created_utc)
                
                # Update cache
                self.channel_configs[channel_id]["last_post_id"] = post.id
                self.channel_configs[channel_id]["last_post_timestamp"] = post.created_utc
                
                logger.info(f"Successfully posted {post.id} to channel {channel_id}")
                
            except Exception as e:
                logger.error(f"Error processing post {post.id}: {e}")
    
    @reddit_fetch_task.before_loop
    async def before_reddit_fetch_task(self):
        """Wait for bot to be ready before starting task"""
        await self.wait_until_ready()

# Create bot instance
bot = RedditBot()

async def main():
    """Main entry point"""
    try:
        await bot.start(bot.settings.discord_token)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        raise
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
        raise