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

    @app_commands.command(name="server_stats", description="Show statistics for this Discord server")
    @app_commands.default_permissions(manage_guild=True)
    async def server_stats(self, interaction: discord.Interaction):
        """Display statistics for the current Discord server"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild.id)
            
            # Get subscriptions for this server
            server_subscriptions = []
            subreddit_list = []
            
            for channel_id, config in self.bot.channel_configs.items():
                if config.get("guild_id") == guild_id:
                    channel = interaction.guild.get_channel(int(channel_id))
                    if channel:
                        server_subscriptions.append({
                            "channel": channel.name,
                            "subreddit": config.get("subreddit"),
                            "bot_name": config.get("bot_name"),
                            "added_by": config.get("added_by_user", "Unknown"),
                            "last_post": config.get("last_post_timestamp")
                        })
                        subreddit_list.append(config.get("subreddit"))
            
            # Get unique subreddits
            unique_subreddits = len(set(subreddit_list))
            
            # Create detailed embed
            embed = discord.Embed(
                title=f"📊 Server Statistics - {interaction.guild.name}",
                color=discord.Color.green()
            )
            
            # Server info
            embed.add_field(
                name="🏰 Server Info",
                value=f"**Members:** {interaction.guild.member_count:,}\n**Owner:** {interaction.guild.owner.mention if interaction.guild.owner else 'Unknown'}\n**Created:** {interaction.guild.created_at.strftime('%Y-%m-%d')}",
                inline=True
            )
            
            # Bot usage in this server
            embed.add_field(
                name="🤖 Bot Usage",
                value=f"**Active Subscriptions:** {len(server_subscriptions)}\n**Unique Subreddits:** {unique_subreddits}\n**Total Channels:** {len(interaction.guild.channels)}",
                inline=True
            )
            
            # Recent activity
            recent_subs = sorted(server_subscriptions, key=lambda x: x.get('last_post', 0), reverse=True)[:5]
            if recent_subs:
                activity_text = ""
                for sub in recent_subs:
                    if sub.get('last_post'):
                        from datetime import datetime
                        try:
                            last_time = datetime.fromtimestamp(float(sub['last_post'])).strftime('%m/%d %H:%M')
                            activity_text += f"#{sub['channel']} (r/{sub['subreddit']}) - {last_time}\n"
                        except:
                            activity_text += f"#{sub['channel']} (r/{sub['subreddit']}) - Unknown\n"
                    else:
                        activity_text += f"#{sub['channel']} (r/{sub['subreddit']}) - No posts yet\n"
                
                embed.add_field(
                    name="📈 Recent Activity",
                    value=activity_text[:1024] if activity_text else "No recent activity",
                    inline=False
                )
            
            # Most followed subreddits in this server
            if subreddit_list:
                from collections import Counter
                subreddit_counts = Counter(subreddit_list)
                popular_subs = subreddit_counts.most_common(5)
                
                popular_text = ""
                for sub, count in popular_subs:
                    popular_text += f"r/{sub} ({count} channel{'s' if count > 1 else ''})\n"
                
                embed.add_field(
                    name="🔥 Popular Subreddits",
                    value=popular_text,
                    inline=True
                )
            
            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            embed.set_footer(text=f"Server ID: {interaction.guild.id}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in server_stats command: {e}")
            await interaction.followup.send(f"Failed to get server stats: {e}", ephemeral=True)

async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(BotManagement(bot))