"""
Discord slash commands for Reddit bot
Separated from main bot.py for better organization.
"""

import logging
import discord
from discord import app_commands

logger = logging.getLogger(__name__)

def setup_commands(bot):
    """Setup all slash commands for the bot"""
    
    @bot.tree.command(name="subscribe", description="Subscribe a channel to a subreddit")
    @app_commands.describe(subreddit="The subreddit to subscribe to", channel="The channel to post updates in (optional, defaults to current channel)")
    async def subscribe(interaction: discord.Interaction, subreddit: str, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        
        # Default to current channel if not specified
        if channel is None:
            channel = interaction.channel
        
        try:
            # Fetch subreddit details
            subreddit_details = await bot.reddit_service.fetch_subreddit_details(subreddit)
            
            # Create or update webhook
            webhook_url = await bot.webhook_service.get_or_create_webhook(
                channel=channel,
                bot_user=bot.user,
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
            
            # Update database and cache with server info
            config_data = {
                "subreddit": subreddit,
                "webhook_url": webhook_url,
                "bot_name": subreddit_details["name"],
                "bot_avatar": subreddit_details["icon"],
                "guild_id": str(channel.guild.id),
                "guild_name": channel.guild.name,
                "channel_name": channel.name,
                "added_by_user": f"{interaction.user.name}#{interaction.user.discriminator}",
            }
            
            await bot.update_channel_config_cache(str(channel.id), config_data)
            
            await interaction.followup.send(
                f"Successfully subscribed to r/{subreddit} in {channel.mention}!", 
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in subscribe command: {e}")
            await interaction.followup.send(f"Failed to subscribe: {e}", ephemeral=True)

    @bot.tree.command(name="unsubscribe", description="Unsubscribe a channel from its subreddit")
    async def unsubscribe(interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        
        try:
            channel_id = str(channel.id)
            
            # Delete from database
            await bot.db_manager.delete_channel_config(channel_id)
            
            # Remove from cache
            bot.channel_configs.pop(channel_id, None)
            
            await interaction.followup.send(f"Unsubscribed {channel.mention} successfully!", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in unsubscribe command: {e}")
            await interaction.followup.send(f"Failed to unsubscribe: {e}", ephemeral=True)

    @bot.tree.command(name="change_avatar", description="Change the bot's avatar for a specific channel")
    @app_commands.describe(channel="The channel to update (optional, defaults to current channel)", image_url="URL of the new avatar image")
    async def change_avatar(interaction: discord.Interaction, image_url: str, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        
        # Default to current channel if not specified
        if channel is None:
            channel = interaction.channel
        
        try:
            channel_id = str(channel.id)
            
            if channel_id not in bot.channel_configs:
                await interaction.followup.send(f"{channel.mention} is not subscribed to any subreddit.", ephemeral=True)
                return
            
            # Update database and cache
            await bot.update_channel_config_cache(channel_id, {"bot_avatar": image_url})
            
            # Update webhook
            await bot.webhook_service.get_or_create_webhook(
                channel=channel,
                bot_user=bot.user,
                bot_name=bot.channel_configs[channel_id]["bot_name"],
                bot_avatar=image_url
            )
            
            await interaction.followup.send(f"Avatar updated for {channel.mention}!", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in change_avatar command: {e}")
            await interaction.followup.send(f"Failed to change avatar: {e}", ephemeral=True)

    @bot.tree.command(name="change_name", description="Change the bot's name for a specific channel")
    @app_commands.describe(channel="The channel to update", name="The new name for the bot")
    async def change_name(interaction: discord.Interaction, channel: discord.TextChannel, name: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            channel_id = str(channel.id)
            
            if channel_id not in bot.channel_configs:
                await interaction.followup.send(f"{channel.mention} is not subscribed to any subreddit.", ephemeral=True)
                return
            
            # Update database and cache
            await bot.update_channel_config_cache(channel_id, {"bot_name": name})
            
            # Update webhook
            await bot.webhook_service.get_or_create_webhook(
                channel=channel,
                bot_user=bot.user,
                bot_name=name,
                bot_avatar=bot.channel_configs[channel_id]["bot_avatar"]
            )
            
            await interaction.followup.send(f"Name updated to `{name}` for {channel.mention}!", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in change_name command: {e}")
            await interaction.followup.send(f"Failed to change name: {e}", ephemeral=True)

    logger.info("Slash commands registered successfully")