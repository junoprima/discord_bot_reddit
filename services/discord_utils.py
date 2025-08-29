import logging
from typing import List, Optional, Dict, Any
import discord
import aiohttp
from database.manager import DatabaseManager
from services.reddit import RedditService

logger = logging.getLogger(__name__)

class DiscordWebhookService:
    """Discord webhook utilities for sending messages and managing webhooks"""
    
    def __init__(self, db_manager: DatabaseManager, reddit_service: RedditService):
        self.db_manager = db_manager
        self.reddit_service = reddit_service
        self.http_session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """Initialize HTTP session for webhooks"""
        if not self.http_session:
            self.http_session = aiohttp.ClientSession()
    
    async def cleanup(self):
        """Clean up resources"""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
    
    async def get_or_create_webhook(
        self, 
        channel: discord.TextChannel, 
        bot_user: discord.User,
        subreddit_name: str = None,
        bot_name: str = None, 
        bot_avatar: str = None
    ) -> Optional[str]:
        """Get existing webhook or create new one for channel"""
        try:
            await self.initialize()
            
            # Fetch subreddit details if needed
            if subreddit_name and (not bot_name or not bot_avatar):
                subreddit_details = await self.reddit_service.fetch_subreddit_details(subreddit_name)
                bot_name = bot_name or subreddit_details["name"]
                bot_avatar = bot_avatar or subreddit_details["icon"]
            
            # Convert avatar URL to bytes if it's a URL
            avatar_bytes = None
            if bot_avatar and bot_avatar.startswith("http"):
                async with self.http_session.get(bot_avatar) as response:
                    if response.status == 200:
                        avatar_bytes = await response.read()
            
            # Get existing webhooks
            webhooks = await channel.webhooks()
            webhook = next((wh for wh in webhooks if wh.user == bot_user), None)
            
            if webhook:
                # Update existing webhook
                await webhook.edit(name=bot_name, avatar=avatar_bytes)
                logger.info(f"Updated webhook for channel {channel.name}")
            else:
                # Create new webhook
                webhook = await channel.create_webhook(name=bot_name, avatar=avatar_bytes)
                logger.info(f"Created new webhook for channel {channel.name}")
            
            return webhook.url
            
        except discord.errors.Forbidden:
            logger.error(f"Bot lacks permissions to create/edit webhooks in {channel.name}")
        except Exception as e:
            logger.error(f"Failed to get or create webhook for {channel.name}: {e}")
        
        return None
    
    async def send_webhook_message(
        self,
        webhook_url: str,
        embeds: List[discord.Embed],
        username: str = None,
        avatar_url: str = None,
        post_link: str = None
    ):
        """Send message via Discord webhook with auto-recreation on 404"""
        try:
            await self.initialize()
            
            payload = {
                "embeds": [embed.to_dict() for embed in embeds] if embeds else None,
                "username": username,
                "avatar_url": avatar_url,
            }
            
            # Add "View Post" button if post link provided
            if post_link:
                payload["components"] = [
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "label": "View Post",
                                "style": 5,  # Link button
                                "url": post_link,
                            }
                        ],
                    }
                ]
            
            async with self.http_session.post(webhook_url, json=payload) as response:
                if response.status in {200, 204}:
                    logger.debug(f"Message sent successfully via webhook")
                    return True
                elif response.status == 404:
                    # Webhook was deleted, return False to trigger recreation
                    error_text = await response.text()
                    logger.warning(f"Webhook not found (404). Will attempt to recreate. Body: {error_text}")
                    return False
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send webhook message. Status: {response.status}, Body: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending webhook message: {e}")
            return False
    
    async def validate_and_recreate_webhook(
        self,
        channel_id: str,
        bot_instance,
        config: Dict[str, Any]
    ) -> Optional[str]:
        """Validate webhook exists, recreate if needed"""
        try:
            # Get the Discord channel
            channel = bot_instance.get_channel(int(channel_id))
            if not channel:
                logger.error(f"Channel {channel_id} not found")
                return None
            
            # Extract config data
            subreddit = config.get("subreddit")
            bot_name = config.get("bot_name", f"r/{subreddit}")
            bot_avatar = config.get("bot_avatar")
            
            logger.info(f"Recreating webhook for channel {channel.name} (r/{subreddit})")
            
            # Create new webhook
            new_webhook_url = await self.get_or_create_webhook(
                channel=channel,
                bot_user=bot_instance.user,
                subreddit_name=subreddit,
                bot_name=bot_name,
                bot_avatar=bot_avatar
            )
            
            if new_webhook_url:
                # Update database with new webhook URL
                await self.db_manager.update_channel_config(channel_id, {"webhook_url": new_webhook_url})
                logger.info(f"Successfully recreated webhook for channel {channel.name}")
                return new_webhook_url
            else:
                logger.error(f"Failed to recreate webhook for channel {channel.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error recreating webhook for channel {channel_id}: {e}")
            return None

class EmbedBuilder:
    """Utility class for building Discord embeds for Reddit posts"""
    
    @staticmethod
    async def create_post_embeds(post, subreddit_name: str, media_urls: List[str], reddit_service: RedditService) -> List[discord.Embed]:
        """Create Discord embeds for a Reddit post"""
        embeds = []
        
        # Get author avatar
        author_avatar = "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"
        if post.author:
            author_avatar = await reddit_service.fetch_user_avatar(post.author.name)
        
        post_url = f"https://www.reddit.com{post.permalink}"
        author_name = f"u/{post.author.name}" if post.author else "Anonymous"
        
        if media_urls:
            # Create embeds for media posts (limit to 4 images per Discord message limit)
            for image_url in media_urls[:4]:
                embed = discord.Embed(
                    title=post.title[:256],  # Discord title limit
                    url=post_url,
                    color=discord.Color.blue()
                )
                embed.set_author(name=author_name, icon_url=author_avatar)
                embed.set_image(url=image_url)
                embed.set_footer(text=f"r/{subreddit_name}")
                embeds.append(embed)
                
        elif post.selftext:
            # Text post with content
            embed = discord.Embed(
                title=post.title[:256],
                url=post_url,
                description=post.selftext[:2048],  # Discord description limit
                color=discord.Color.blue()
            )
            embed.set_author(name=author_name, icon_url=author_avatar)
            embed.set_footer(text=f"r/{subreddit_name}")
            embeds.append(embed)
            
        else:
            # Link post or post with no content
            embed = discord.Embed(
                title=post.title[:256],
                url=post_url,
                color=discord.Color.blue()
            )
            embed.set_author(name=author_name, icon_url=author_avatar)
            embed.set_footer(text=f"r/{subreddit_name}")
            
            # Add external link if it's not a Reddit link
            if post.url and not post.url.startswith("https://www.reddit.com"):
                embed.add_field(name="External Link", value=f"[Click here]({post.url})", inline=False)
            
            embeds.append(embed)
        
        return embeds