import asyncpraw
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import logging
from dotenv import load_dotenv
import asyncio
import aiohttp
from firebase_admin import credentials, firestore, initialize_app
from discord.ui import Button, View
from asyncprawcore import Requestor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/discord_slash_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

if not all([DISCORD_TOKEN, FIREBASE_CREDENTIALS, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT]):
    logger.error("Missing one or more environment variables.")
    exit(1)

# Initialize Firebase Admin SDK
try:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS)
    initialize_app(cred)
    firestore_client = firestore.client()
    logger.info("Firebase initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")
    exit(1)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

http_session = None  # Global aiohttp.ClientSession instance
last_post_ids = {}  # Track last post IDs for each subreddit
channel_configs = {}

async def get_channel_config(channel_id: str):
    """
    Fetch the Firestore configuration for a given channel ID.
    """
    try:
        docs = firestore_client.collection("channel_configs").where("channel_id", "==", channel_id).stream()
        return next(docs, None)
    except Exception as e:
        logger.error(f"Error fetching configuration for channel {channel_id}: {e}")
        return None


async def update_channel_config(channel_id: str, data: dict):
    """
    Update or set the Firestore configuration for a given channel ID.
    """
    try:
        doc = await get_channel_config(channel_id)
        if doc:
            doc.reference.update(data)
        else:
            firestore_client.collection("channel_configs").document(channel_id).set(data, merge=True)
    except Exception as e:
        logger.error(f"Error updating configuration for channel {channel_id}: {e}")


async def reload_channel_config(channel_id: str):
    """
    Reload a single channel configuration into the cache.
    """
    global channel_configs
    try:
        doc = await get_channel_config(channel_id)
        if doc:
            channel_configs[channel_id] = doc.to_dict()
            logger.info(f"Configuration for channel {channel_id} reloaded.")
    except Exception as e:
        logger.error(f"Failed to reload channel configuration for {channel_id}: {e}")


async def load_channel_configs():
    """
    Load all channel configurations from Firestore into a global cache.
    """
    global channel_configs
    try:
        configs = firestore_client.collection("channel_configs").stream()
        for config in configs:
            data = config.to_dict()
            channel_configs[data['channel_id']] = data
        logger.info("Channel configurations cached successfully.")
    except Exception as e:
        logger.error(f"Failed to cache channel configurations: {e}")



# Helper: Fetch Reddit avatar
async def fetch_reddit_avatar(username):
    default_avatar = "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"
    url = f"https://www.reddit.com/user/{username}/about.json"

    try:
        async with http_session.get(url, headers={"User-Agent": "RedditBot"}) as response:
            if response.status == 200:
                data = await response.json()
                avatar_url = data["data"].get("icon_img", default_avatar)
                return avatar_url.split('?')[0]  # Clean URL
    except Exception as e:
        logger.error(f"Error fetching avatar for {username}: {e}")
    return default_avatar


# Helper: Create embeds
async def create_embeds(post, subreddit_name, media_urls):
    author_avatar = await fetch_reddit_avatar(post.author.name) if post.author else \
        "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"

    embeds = []
    for idx, image_url in enumerate(media_urls[:4]):  # Limit to 4 images
        embed = discord.Embed(
            title=post.title,
            url=f"https://www.reddit.com{post.permalink}",
            color=discord.Color.blue()
        )
        embed.set_author(name=f"{post.author.name}", icon_url=author_avatar)
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Subreddit: r/{subreddit_name}")
        embeds.append(embed)
    return embeds


# Slash Command: Subscribe to a subreddit
@tree.command(name="subscribe", description="Subscribe a channel to a subreddit")
@app_commands.describe(subreddit="The subreddit to subscribe to", channel="The channel to post updates in")
async def subscribe(interaction: discord.Interaction, subreddit: str, channel: discord.TextChannel):
    try:
        bot_avatar = bot.user.avatar.url if bot.user.avatar else "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"
        await update_channel_config(str(channel.id), {
            "channel_id": str(channel.id),
            "subreddit": subreddit,
            "bot_name": bot.user.name,
            "bot_avatar": bot_avatar,
        })
        
        # Refresh cache
        await reload_channel_config(str(channel.id))

        await interaction.response.send_message(f"Successfully subscribed `{channel.name}` to `r/{subreddit}`!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error subscribing: {e}", ephemeral=True)
        logger.error(f"Error in subscribe command: {e}")


# Slash Command: Unsubscribe from a subreddit
@tree.command(name="unsubscribe", description="Unsubscribe a channel from its subreddit")
@app_commands.describe(channel="The channel to unsubscribe")
async def unsubscribe(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        docs = firestore_client.collection("channel_configs").where("channel_id", "==", str(channel.id)).stream()
        for doc in docs:
            doc.reference.delete()
            await interaction.response.send_message(f"Unsubscribed `{channel.name}` successfully!", ephemeral=True)
            return
        await interaction.response.send_message("No subscription found for this channel.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error unsubscribing: {e}", ephemeral=True)
        logger.error(f"Error in unsubscribe command: {e}")
        

@tree.command(name="change_avatar", description="Change the bot's avatar for a specific channel")
@app_commands.describe(channel="The channel to update the avatar for", image_url="URL of the new avatar image")
async def change_avatar(interaction: discord.Interaction, channel: discord.TextChannel, image_url: str):
    await interaction.response.defer(ephemeral=True)
    try:
        # Update Firestore
        await update_channel_config(str(channel.id), {"bot_avatar": image_url})
        
        # Refresh cache
        await reload_channel_config(str(channel.id))

        # Re-create webhook if necessary
        bot_name = channel_configs.get(str(channel.id), {}).get("bot_name", bot.user.name)
        await get_or_create_webhook(channel, bot_name, image_url)

        await interaction.followup.send(f"Avatar updated for `{channel.name}`!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error changing avatar: {e}", ephemeral=True)
        logger.error(f"Error in change_avatar command: {e}")



@tree.command(name="change_name", description="Change the bot's name for a specific channel")
@app_commands.describe(channel="The channel to update the name for", name="The new name for the bot")
async def change_name(interaction: discord.Interaction, channel: discord.TextChannel, name: str):
    await interaction.response.defer(ephemeral=True)
    try:
        # Update Firestore
        await update_channel_config(str(channel.id), {"bot_name": name})
        
        # Refresh cache
        await reload_channel_config(str(channel.id))

        # Re-create webhook if necessary
        avatar_url = channel_configs.get(str(channel.id), {}).get("bot_avatar", None)
        await get_or_create_webhook(channel, name, avatar_url)

        await interaction.followup.send(f"Name updated to `{name}` for `{channel.name}`!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error changing name: {e}", ephemeral=True)
        logger.error(f"Error in change_name command: {e}")



async def get_or_create_webhook(channel: discord.TextChannel, bot_name: str, bot_avatar: str):
    """
    Retrieve or create a webhook for the channel, then update Firestore.
    """
    try:
        if channel.id in channel_configs and channel_configs[channel.id].get("webhook_url"):
            webhook_url = channel_configs[channel.id]["webhook_url"]
            # Validate existing webhook
            try:
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(webhook_url, session=session)
                    await webhook.fetch()  # Ensure it's valid
                return webhook_url
            except discord.NotFound:
                logger.warning(f"Webhook not found for channel {channel.id}. Recreating...")

        # Create a new webhook
        webhooks = await channel.webhooks()
        webhook = next((wh for wh in webhooks if wh.user == bot.user), None)
        if not webhook:
            webhook = await channel.create_webhook(name=bot_name)

        # Update Firestore and cache
        webhook_url = webhook.url
        await update_channel_config(str(channel.id), {
            "webhook_url": webhook_url,
            "bot_name": bot_name,
            "bot_avatar": bot_avatar,
        })
        channel_configs[channel.id]["webhook_url"] = webhook_url
        return webhook_url
    except Exception as e:
        logger.error(f"Failed to create webhook for channel {channel.name}: {e}")
        return None

async def send_message_with_webhook(channel: discord.TextChannel, message: str, embeds=None):
    try:
        webhook_url = channel_configs[channel.id]["webhook_url"]
        bot_name = channel_configs[channel.id].get("bot_name", "DefaultBot")
        bot_avatar = channel_configs[channel.id].get("bot_avatar", "https://default.avatar.url/image.png")

        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(webhook_url, adapter=discord.AsyncWebhookAdapter(session))
            await webhook.send(content=message, username=bot_name, avatar_url=bot_avatar, embeds=embeds)
    except discord.errors.RateLimited as e:
        logger.warning(f"Rate limited while sending message to {channel.name}: {e}")
        await asyncio.sleep(e.retry_after)
        await send_message_with_webhook(channel, message, embeds)
    except Exception as e:
        logger.error(f"Failed to send message with webhook in {channel.name}: {e}")


# Task to fetch posts for each configured subreddit
@tasks.loop(minutes=1)
async def fetch_reddit_posts(subreddit_name: str, last_post_id: str = None):
    """
    Fetch new Reddit posts from a subreddit, optionally filtering by last_post_id.
    """
    try:
        reddit = asyncpraw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            requestor=Requestor("aiohttp", session=http_session),
        )
        subreddit = await reddit.subreddit(subreddit_name)
        posts = []
        async for post in subreddit.new(limit=10):
            if last_post_id and post.id <= last_post_id:
                break
            posts.append(post)
        return posts
    except Exception as e:
        logger.error(f"Failed to fetch posts from r/{subreddit_name}: {e}")
        return []



async def send_custom_message(channel: discord.TextChannel, content=None, embed=None):
    # Fetch channel-specific settings
    channel_id = str(channel.id)
    bot_name = channel_configs.get(channel_id, {}).get("bot_name", bot.user.name)
    bot_avatar = channel_configs.get(channel_id, {}).get("bot_avatar", bot.user.avatar.url)

    # Update the bot's name dynamically (temporary change for this channel)
    try:
        if bot_name != bot.user.name:
            await bot.user.edit(username=bot_name)
    except discord.HTTPException as e:
        logger.error(f"Failed to change bot name: {e}")

    # Send the message
    try:
        if content:
            await channel.send(content)
        if embed:
            await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Error sending message to channel {channel.name}: {e}")

    # Revert the bot's name to avoid global impact
    try:
        if bot_name != bot.user.name:
            await bot.user.edit(username=bot.user.name)
    except discord.HTTPException as e:
        logger.error(f"Failed to revert bot name: {e}")


# Example of sending a message
@tree.command(name="test_message", description="Send a test message with per-channel customization")
async def test_message(interaction: discord.Interaction):
    try:
        # Defer the interaction to acknowledge the command
        await interaction.response.defer(ephemeral=True)

        # Fetch the channel-specific configuration from Firestore
        docs = firestore_client.collection("channel_configs").where("channel_id", "==", str(interaction.channel_id)).stream()
        for doc in docs:
            config = doc.to_dict()
            webhook_url = config.get("webhook_url")
            bot_name = config.get("bot_name", "Default_Bot_Name")
            bot_avatar = config.get("bot_avatar", None)

            if not webhook_url:
                await interaction.followup.send("No webhook found for this channel.", ephemeral=True)
                return

            # Use aiohttp to send the message via the webhook
            async with aiohttp.ClientSession() as session:
                payload = {
                    "content": f"This is a test message for `{interaction.channel.name}` with per-channel customization!",
                    "username": bot_name,
                    "avatar_url": bot_avatar,
                }
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 204:  # 204 No Content indicates success
                        await interaction.followup.send("Test message sent successfully!", ephemeral=True)
                    else:
                        error_text = await response.text()
                        await interaction.followup.send(f"Failed to send test message. Error: {error_text}", ephemeral=True)
            return  # Exit after processing the first valid configuration

        # If no configuration found
        await interaction.followup.send("No configuration found for this channel.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"Error sending test message: {e}", ephemeral=True)
        logger.error(f"Error in test_message command: {e}")



@bot.event
async def on_ready():
    await load_channel_configs()
    global channel_configs
    try:
        # Fetch channel configurations from Firestore
        configs = firestore_client.collection("channel_configs").stream()
        for config in configs:
            data = config.to_dict()
            channel_configs[data['channel_id']] = {
                'bot_name': data.get('bot_name', bot.user.name),
                'bot_avatar': data.get('bot_avatar', bot.user.avatar.url if bot.user.avatar else None)
            }
        logger.info("Channel configurations cached successfully.")
    except Exception as e:
        logger.error(f"Failed to cache channel configurations: {e}")

    # Sync slash commands
    try:
        await bot.tree.sync()
        logger.info("Slash commands synchronized successfully.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    logger.info(f"Logged in as {bot.user}")


@bot.event
async def on_disconnect():
    global http_session
    if http_session is not None:
        await http_session.close()
        http_session = None
    logger.info("HTTP session closed on disconnect.")


@bot.event
async def on_close():
    global http_session
    if http_session is not None:
        await http_session.close()
    logger.info("Bot is shutting down.")
    exit(0)


# Main entry
async def main():
    global http_session
    http_session = aiohttp.ClientSession()
    try:
        await bot.start(DISCORD_TOKEN)
    finally:
        if http_session:
            await http_session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Failed to start the bot: {e}")
