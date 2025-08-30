import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

logger = logging.getLogger(__name__)

class BotManagement(commands.Cog):
    """Bot management and customization commands"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="change_avatar", description="Change the bot's avatar for a specific channel")
    @app_commands.describe(
        image_url="URL of the new avatar image",
        channel="The channel to update (optional, defaults to current channel)"
    )
    async def change_avatar(self, interaction: discord.Interaction, image_url: str, channel: Optional[discord.TextChannel] = None):
        """Change bot avatar for a specific channel's webhook"""
        await interaction.response.defer(ephemeral=True)
        
        # Default to current channel if not specified
        if channel is None:
            channel = interaction.channel
        
        try:
            channel_id = str(channel.id)
            
            if channel_id not in self.bot.channel_configs:
                await interaction.followup.send(
                    f"{channel.mention} is not subscribed to any subreddit.", 
                    ephemeral=True
                )
                return
            
            # Update database and cache
            await self.bot.update_channel_config_cache(channel_id, {"bot_avatar": image_url})
            
            # Update webhook
            await self.bot.webhook_service.get_or_create_webhook(
                channel=channel,
                bot_user=self.bot.user,
                bot_name=self.bot.channel_configs[channel_id]["bot_name"],
                bot_avatar=image_url
            )
            
            await interaction.followup.send(f"Avatar updated for {channel.mention}!", ephemeral=True)
            logger.info(f"🎨 Avatar updated for channel {channel.name} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error in change_avatar command: {e}")
            await interaction.followup.send(f"Failed to change avatar: {e}", ephemeral=True)

    @app_commands.command(name="change_name", description="Change the bot's name for a specific channel")
    @app_commands.describe(
        channel="The channel to update",
        name="The new name for the bot"
    )
    async def change_name(self, interaction: discord.Interaction, channel: discord.TextChannel, name: str):
        """Change bot name for a specific channel's webhook"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            channel_id = str(channel.id)
            
            if channel_id not in self.bot.channel_configs:
                await interaction.followup.send(
                    f"{channel.mention} is not subscribed to any subreddit.", 
                    ephemeral=True
                )
                return
            
            # Update database and cache
            await self.bot.update_channel_config_cache(channel_id, {"bot_name": name})
            
            # Update webhook
            await self.bot.webhook_service.get_or_create_webhook(
                channel=channel,
                bot_user=self.bot.user,
                bot_name=name,
                bot_avatar=self.bot.channel_configs[channel_id]["bot_avatar"]
            )
            
            await interaction.followup.send(f"Name updated to `{name}` for {channel.mention}!", ephemeral=True)
            logger.info(f"📝 Name updated to '{name}' for channel {channel.name} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error in change_name command: {e}")
            await interaction.followup.send(f"Failed to change name: {e}", ephemeral=True)

    @app_commands.command(name="bot_info", description="Show information about the bot")
    async def bot_info(self, interaction: discord.Interaction):
        """Display bot information and statistics"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Gather bot statistics
            total_subscriptions = len(self.bot.channel_configs)
            total_servers = len(self.bot.guilds)
            
            # Count unique subreddits
            unique_subreddits = len(set(
                config.get("subreddit") for config in self.bot.channel_configs.values()
                if config.get("subreddit")
            ))
            
            # Get server-specific stats
            guild_id = str(interaction.guild.id)
            server_subscriptions = sum(
                1 for config in self.bot.channel_configs.values()
                if config.get("guild_id") == guild_id
            )
            
            embed = discord.Embed(
                title="🤖 Reddit Bot Information",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📊 Global Stats",
                value=f"**Servers:** {total_servers}\n**Total Subscriptions:** {total_subscriptions}\n**Unique Subreddits:** {unique_subreddits}",
                inline=True
            )
            
            embed.add_field(
                name="🏰 This Server",
                value=f"**Subscriptions:** {server_subscriptions}",
                inline=True
            )
            
            embed.add_field(
                name="🔗 Commands",
                value="**/subscribe** - Add subreddit to channel\n**/unsubscribe** - Remove subscription\n**/list_subscriptions** - View all subscriptions",
                inline=False
            )
            
            embed.set_footer(text=f"Bot ID: {self.bot.user.id}")
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in bot_info command: {e}")
            await interaction.followup.send(f"Failed to get bot info: {e}", ephemeral=True)

async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(BotManagement(bot))