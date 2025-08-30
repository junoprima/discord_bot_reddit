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

    @app_commands.command(name="bot_status", description="Show detailed bot status (Admin only)")
    @is_bot_owner()
    async def bot_status(self, interaction: discord.Interaction):
        """Show detailed bot status and health"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get bot statistics
            total_servers = len(self.bot.guilds)
            total_channels = len(self.bot.channel_configs)
            
            # Get memory info (basic)
            try:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024
            except ImportError:
                memory_mb = 0  # psutil not available
            
            embed = discord.Embed(
                title="🤖 Bot Status Dashboard",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 Statistics",
                value=f"**Servers:** {total_servers}\n**Active Channels:** {total_channels}\n**Memory Usage:** {memory_mb:.1f} MB",
                inline=True
            )
            
            embed.add_field(
                name="🔧 Services",
                value=f"**Reddit Service:** {'✅' if self.bot.reddit_service else '❌'}\n**Webhook Service:** {'✅' if self.bot.webhook_service else '❌'}\n**Database:** {'✅' if self.bot.db_manager else '❌'}",
                inline=True
            )
            
            embed.add_field(
                name="⚡ Tasks",
                value=f"**Reddit Fetch Task:** {'✅ Running' if hasattr(self.bot, 'reddit_fetch_task') and not self.bot.reddit_fetch_task.is_being_cancelled() else '❌ Stopped'}",
                inline=True
            )
            
            # Get recent activity
            try:
                # This would require implementing a method to get recent post count
                embed.add_field(
                    name="📈 Activity",
                    value="Recent activity data available via database queries",
                    inline=False
                )
            except:
                pass
            
            embed.set_footer(text=f"Bot Uptime: {self.bot.uptime if hasattr(self.bot, 'uptime') else 'Unknown'}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in bot_status command: {e}")
            await interaction.followup.send(f"Failed to get bot status: {e}", ephemeral=True)

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

    @app_commands.command(name="server_analytics", description="Show detailed server analytics (Admin only)")
    @is_bot_owner()
    async def server_analytics(self, interaction: discord.Interaction):
        """Display comprehensive server analytics dashboard"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get server analytics data
            analytics_data = await self.bot.db_manager.get_server_analytics()
            
            if not analytics_data:
                await interaction.followup.send(
                    "No server analytics data available yet. Make sure to run the server tracking migration first.", 
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="📊 Discord Server Analytics Dashboard",
                color=discord.Color.gold()
            )
            
            # Summary stats
            total_servers = len(analytics_data)
            total_members = sum(server.get('member_count', 0) for server in analytics_data)
            total_subscriptions = sum(server.get('active_subscriptions', 0) for server in analytics_data)
            
            embed.add_field(
                name="📈 Overview",
                value=f"**Total Servers:** {total_servers}\n**Total Members:** {total_members:,}\n**Total Subscriptions:** {total_subscriptions}",
                inline=True
            )
            
            # Top servers by members
            top_servers = sorted(analytics_data, key=lambda x: x.get('member_count', 0), reverse=True)[:5]
            top_servers_text = ""
            for i, server in enumerate(top_servers, 1):
                name = server.get('guild_name', 'Unknown')[:20]
                members = server.get('member_count', 0)
                subs = server.get('active_subscriptions', 0)
                top_servers_text += f"{i}. **{name}** - {members:,} members, {subs} subs\n"
            
            embed.add_field(
                name="🏆 Top Servers by Members",
                value=top_servers_text or "No data available",
                inline=True
            )
            
            # Most active servers by subscriptions
            active_servers = sorted(analytics_data, key=lambda x: x.get('active_subscriptions', 0), reverse=True)[:5]
            active_servers_text = ""
            for i, server in enumerate(active_servers, 1):
                if server.get('active_subscriptions', 0) > 0:
                    name = server.get('guild_name', 'Unknown')[:20]
                    subs = server.get('active_subscriptions', 0)
                    members = server.get('member_count', 0)
                    active_servers_text += f"{i}. **{name}** - {subs} subs, {members:,} members\n"
            
            embed.add_field(
                name="⚡ Most Active Servers",
                value=active_servers_text or "No active servers",
                inline=False
            )
            
            embed.set_footer(text=f"Data from {len(self.bot.guilds)} connected servers")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in server_analytics command: {e}")
            await interaction.followup.send(f"Failed to get server analytics: {e}", ephemeral=True)

    @app_commands.command(name="update_server_info", description="Update server information for all connected servers (Admin only)")
    @is_bot_owner()
    async def update_server_info(self, interaction: discord.Interaction):
        """Force update server information for all connected servers"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            updated_count = 0
            
            for guild in self.bot.guilds:
                try:
                    await self.bot._record_server_info(guild)
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Failed to update server info for {guild.name}: {e}")
            
            await interaction.followup.send(
                f"✅ Updated server information for {updated_count}/{len(self.bot.guilds)} servers", 
                ephemeral=True
            )
            logger.info(f"Server info updated by {interaction.user}: {updated_count} servers")
            
        except Exception as e:
            logger.error(f"Error updating server info: {e}")
            await interaction.followup.send(f"Failed to update server info: {e}", ephemeral=True)

    @app_commands.command(name="setup_analytics", description="Setup server analytics database (Admin only)")
    @is_bot_owner()
    async def setup_analytics(self, interaction: discord.Interaction):
        """Setup server analytics database schema"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Import and run the simple server tracking migration
            import sqlite3
            import os
            
            db_path = self.bot.settings.database_path
            if not os.path.exists(db_path):
                await interaction.followup.send("❌ Database file not found!", ephemeral=True)
                return
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check existing columns
            cursor.execute("PRAGMA table_info(channel_configs)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Add server tracking columns
            simple_columns = [
                ("guild_id", "TEXT"),
                ("guild_name", "TEXT"), 
                ("channel_name", "TEXT"),
                ("server_owner_id", "TEXT"),
                ("server_owner_name", "TEXT"),
                ("server_member_count", "INTEGER"),
                ("server_created_at", "TEXT"),
                ("bot_joined_at", "TEXT"),
                ("added_by_user", "TEXT"),
                ("server_region", "TEXT"),
                ("server_verification_level", "INTEGER"),
                ("total_server_channels", "INTEGER"),
            ]
            
            added_count = 0
            
            for col_name, col_type in simple_columns:
                if col_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE channel_configs ADD COLUMN {col_name} {col_type}")
                        added_count += 1
                    except Exception as e:
                        logger.error(f"Failed to add column {col_name}: {e}")
            
            # Create server analytics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    guild_name TEXT,
                    member_count INTEGER DEFAULT 0,
                    total_channels INTEGER DEFAULT 0,
                    total_subscriptions INTEGER DEFAULT 0,
                    bot_added_at TEXT,
                    last_updated TEXT,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE(guild_id) ON CONFLICT REPLACE
                )
            """)
            
            # Create indexes
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_channel_configs_guild ON channel_configs(guild_id)",
                "CREATE INDEX IF NOT EXISTS idx_server_analytics_guild ON server_analytics(guild_id)",
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            conn.commit()
            conn.close()
            
            # Update current server info
            for guild in self.bot.guilds:
                await self.bot._record_server_info(guild)
            
            await interaction.followup.send(
                f"✅ Server analytics setup complete!\n"
                f"• Added {added_count} new columns\n"
                f"• Created server_analytics table\n"
                f"• Updated info for {len(self.bot.guilds)} servers\n"
                f"• Use `/server_analytics` to view data", 
                ephemeral=True
            )
            
            logger.info(f"Server analytics setup completed by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error setting up analytics: {e}")
            await interaction.followup.send(f"Failed to setup analytics: {e}", ephemeral=True)

    @force_sync.error
    @reload_cogs.error
    @bot_status.error
    @force_refresh.error
    @server_analytics.error
    @update_server_info.error
    @setup_analytics.error
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