import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)

class AdminCommands(commands.Cog):
    """Admin-only commands for bot management and debugging"""
    
    def __init__(self, bot):
        self.bot = bot

    def is_bot_owner():
        """Check if user is bot owner"""
        async def predicate(interaction: discord.Interaction):
            # You can customize this check - for now, server owner or bot owner
            return (
                interaction.user.id == interaction.guild.owner_id or 
                await interaction.client.is_owner(interaction.user)
            )
        return app_commands.check(predicate)

    @app_commands.command(name="force_sync", description="Force sync slash commands (Admin only)")
    @is_bot_owner()
    async def force_sync(self, interaction: discord.Interaction):
        """Force sync all slash commands"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(
                f"Successfully synced {len(synced)} commands!", 
                ephemeral=True
            )
            logger.info(f"Commands synced by {interaction.user}: {len(synced)} commands")
            
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")
            await interaction.followup.send(f"Failed to sync commands: {e}", ephemeral=True)

    @app_commands.command(name="reload_cogs", description="Reload all cogs (Admin only)")
    @is_bot_owner()
    async def reload_cogs(self, interaction: discord.Interaction):
        """Reload all bot cogs"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get list of loaded cogs
            cog_names = list(self.bot.cogs.keys())
            reloaded = []
            failed = []
            
            for cog_name in cog_names:
                try:
                    await self.bot.reload_extension(f"cogs.{cog_name.lower().replace(' ', '_')}")
                    reloaded.append(cog_name)
                except Exception as e:
                    failed.append(f"{cog_name}: {str(e)}")
            
            result = f"**Reloaded:** {len(reloaded)} cogs"
            if reloaded:
                result += f"\n✅ {', '.join(reloaded)}"
            
            if failed:
                result += f"\n❌ **Failed:** {len(failed)}\n{chr(10).join(failed)}"
            
            await interaction.followup.send(result, ephemeral=True)
            logger.info(f"Cogs reloaded by {interaction.user}: {len(reloaded)} success, {len(failed)} failed")
            
        except Exception as e:
            logger.error(f"Error reloading cogs: {e}")
            await interaction.followup.send(f"Failed to reload cogs: {e}", ephemeral=True)


    @app_commands.command(name="force_refresh", description="Force refresh channel configs (Admin only)")
    @is_bot_owner()
    async def force_refresh(self, interaction: discord.Interaction):
        """Force refresh all channel configurations"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Reload channel configs
            await self.bot.load_channel_configs()
            
            await interaction.followup.send(
                f"✅ Refreshed {len(self.bot.channel_configs)} channel configurations", 
                ephemeral=True
            )
            logger.info(f"Channel configs refreshed by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error refreshing configs: {e}")
            await interaction.followup.send(f"Failed to refresh configs: {e}", ephemeral=True)


    @force_sync.error
    @reload_cogs.error
    @force_refresh.error
    async def admin_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors in admin commands"""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command. (Admin only)", 
                ephemeral=True
            )
        else:
            logger.error(f"Admin command error: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)

async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(AdminCommands(bot))