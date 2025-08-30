import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

logger = logging.getLogger(__name__)

class RedditCommands(commands.Cog):
    """Reddit-related Discord commands (subscribe, unsubscribe, etc.)"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="subscribe", description="Subscribe a channel to a subreddit")
    @app_commands.describe(
        subreddit="The subreddit to subscribe to", 
        channel="The channel to post updates in (optional, defaults to current channel)"
    )
    async def subscribe(self, interaction: discord.Interaction, subreddit: str, channel: Optional[discord.TextChannel] = None):
        """Subscribe a channel to Reddit posts from a specific subreddit"""
        await interaction.response.defer(ephemeral=True)
        
        # Default to current channel if not specified
        if channel is None:
            channel = interaction.channel
        
        try:
            # Fetch subreddit details
            subreddit_details = await self.bot.reddit_service.fetch_subreddit_details(subreddit)
            
            # Create or update webhook
            webhook_url = await self.bot.webhook_service.get_or_create_webhook(
                channel=channel,
                bot_user=self.bot.user,
                subreddit_name=subreddit,
                bot_name=subreddit_details["name"],
                bot_avatar=subreddit_details["icon"]
            )
            
            if not webhook_url:
                await interaction.followup.send(
                    f"Failed to create webhook for {channel.mention}. Check permissions.", 
                    ephemeral=True
                )
                return
            
            # Update database and cache with comprehensive server info
            config_data = {
                "subreddit": subreddit,
                "webhook_url": webhook_url,
                "bot_name": subreddit_details["name"],
                "bot_avatar": subreddit_details["icon"],
                "guild_id": str(channel.guild.id),
                "guild_name": channel.guild.name,
                "channel_name": channel.name,
                "added_by_user": f"{interaction.user.name}#{interaction.user.discriminator}",
                "server_owner_id": str(channel.guild.owner_id) if channel.guild.owner_id else None,
                "server_owner_name": channel.guild.owner.name if channel.guild.owner else None,
                "server_member_count": channel.guild.member_count,
                "server_created_at": channel.guild.created_at.isoformat(),
                "server_region": str(channel.guild.preferred_locale) if channel.guild.preferred_locale else None,
                "server_verification_level": channel.guild.verification_level.value,
                "total_server_channels": len(channel.guild.channels),
            }
            
            await self.bot.update_channel_config_cache(str(channel.id), config_data)
            
            await interaction.followup.send(
                f"Successfully subscribed to r/{subreddit} in {channel.mention}!", 
                ephemeral=True
            )
            
            logger.info(f"📺 Channel {channel.name} ({channel.id}) subscribed to r/{subreddit} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error in subscribe command: {e}")
            await interaction.followup.send(f"Failed to subscribe: {e}", ephemeral=True)

    @app_commands.command(name="unsubscribe", description="Unsubscribe a channel from its subreddit")
    @app_commands.describe(channel="The channel to unsubscribe")
    async def unsubscribe(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Unsubscribe a channel from Reddit posts"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            channel_id = str(channel.id)
            
            # Check if channel is subscribed
            if channel_id not in self.bot.channel_configs:
                await interaction.followup.send(
                    f"{channel.mention} is not subscribed to any subreddit.", 
                    ephemeral=True
                )
                return
            
            subreddit = self.bot.channel_configs[channel_id].get("subreddit", "unknown")
            
            # Delete from database
            await self.bot.db_manager.delete_channel_config(channel_id)
            
            # Remove from cache
            self.bot.channel_configs.pop(channel_id, None)
            
            await interaction.followup.send(
                f"Unsubscribed {channel.mention} from r/{subreddit}!", 
                ephemeral=True
            )
            
            logger.info(f"📺 Channel {channel.name} ({channel.id}) unsubscribed from r/{subreddit} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error in unsubscribe command: {e}")
            await interaction.followup.send(f"Failed to unsubscribe: {e}", ephemeral=True)

    @app_commands.command(name="list_subscriptions", description="List all active subscriptions in this server")
    async def list_subscriptions(self, interaction: discord.Interaction):
        """List all subscriptions in the current server"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild.id)
            
            # Get subscriptions for this server
            server_subscriptions = []
            for channel_id, config in self.bot.channel_configs.items():
                if config.get("guild_id") == guild_id:
                    channel = interaction.guild.get_channel(int(channel_id))
                    if channel:
                        server_subscriptions.append({
                            "channel": channel.name,
                            "subreddit": config.get("subreddit"),
                            "bot_name": config.get("bot_name"),
                            "added_by": config.get("added_by_user", "Unknown")
                        })
            
            if not server_subscriptions:
                await interaction.followup.send(
                    "No active subscriptions in this server.", 
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title=f"📺 Active Subscriptions in {interaction.guild.name}",
                description=f"Total: {len(server_subscriptions)} subscriptions",
                color=discord.Color.blue()
            )
            
            for sub in server_subscriptions[:10]:  # Limit to 10 to avoid embed limits
                embed.add_field(
                    name=f"#{sub['channel']}",
                    value=f"r/{sub['subreddit']}\nBot: {sub['bot_name']}\nAdded by: {sub['added_by']}",
                    inline=True
                )
            
            if len(server_subscriptions) > 10:
                embed.set_footer(text=f"... and {len(server_subscriptions) - 10} more")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in list_subscriptions command: {e}")
            await interaction.followup.send(f"Failed to list subscriptions: {e}", ephemeral=True)

async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(RedditCommands(bot))