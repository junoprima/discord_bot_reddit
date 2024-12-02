import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncpraw
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import aiohttp
import asyncio
from firebase_admin import credentials, firestore, initialize_app
from asyncprawcore.exceptions import ResponseException, NotFound
from urllib.parse import urlparse, urlunparse

# Ensure the logs directory exists
if not os.path.exists("logs"):
    os.makedirs("logs")

# Set up the logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler("logs/reddit_feed_bot.log", maxBytes=5 * 1024 * 1024, backupCount=3),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)

### Load Environment Variables ###
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

if not all([DISCORD_TOKEN, FIREBASE_CREDENTIALS, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT]):
    logger.error("Missing one or more environment variables.")
    exit(1)

### Firebase Setup ###
cred = credentials.Certificate(FIREBASE_CREDENTIALS)
initialize_app(cred)
firestore_client = firestore.client()

### Discord Bot Setup ###
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

### Global Variables ###
http_session = None
reddit_client = None
channel_configs = {}

### Helper Functions ###

async def initialize_http_session():
    global http_session
    if not http_session:
        http_session = aiohttp.ClientSession()

async def initialize_reddit_client():
    global reddit_client
    if not reddit_client:
        reddit_client = asyncpraw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
    return reddit_client

async def load_channel_configs():
    """Load all channel configurations from Firestore into memory."""
    global channel_configs
    try:
        configs = firestore_client.collection("channel_configs").stream()
        for config in configs:
            data = config.to_dict()
            channel_configs[data["channel_id"]] = data
        logger.info("Channel configurations loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load channel configurations: {e}")

async def update_channel_config(channel_id, data):
    """Update a channel's configuration in Firestore and cache."""
    try:
        if "subreddit" in data:
            subreddit_details = await fetch_subreddit_details(data["subreddit"])
            data["bot_name"] = data.get("bot_name", subreddit_details["name"])
            data["bot_avatar"] = data.get("bot_avatar", subreddit_details["icon"])
        firestore_client.collection("channel_configs").document(channel_id).set(data, merge=True)
        channel_configs[channel_id] = data
        logger.info(f"Configuration updated for channel {channel_id}.")
    except Exception as e:
        logger.error(f"Failed to update channel configuration for {channel_id}: {e}")

async def reload_channel_config(channel_id):
    """Reload a single channel's configuration."""
    try:
        doc = firestore_client.collection("channel_configs").document(channel_id).get()
        if doc.exists:
            channel_configs[channel_id] = doc.to_dict()
            logger.info(f"Configuration for channel {channel_id} reloaded.")
        else:
            channel_configs.pop(channel_id, None)
            logger.warning(f"No configuration found for channel {channel_id}.")
    except Exception as e:
        logger.error(f"Failed to reload channel configuration for {channel_id}: {e}")

async def delete_channel_config(channel_id):
    """
    Delete a channel configuration from Firestore and cache.
    """
    try:
        firestore_client.collection("channel_configs").document(channel_id).delete()
        channel_configs.pop(channel_id, None)
        logging.info(f"Configuration deleted for channel {channel_id}.")
    except Exception as e:
        logging.error(f"Failed to delete channel configuration: {e}")


async def fetch_subreddit_details(subreddit_name):
    default_icon = "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"
    try:
        global http_session
        if not http_session:
            http_session = aiohttp.ClientSession()

        url = f"https://www.reddit.com/r/{subreddit_name}/about.json"
        headers = {"User-Agent": "RedditBot"}
        logger.info(f"Fetching subreddit details for r/{subreddit_name} from {url}")

        async with http_session.get(url, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Failed to fetch details for r/{subreddit_name} (HTTP {response.status}): {error_text}")
                return {"name": f"r/{subreddit_name}", "icon": default_icon}

            data = await response.json()
            #logger.debug(f"Raw API response for r/{subreddit_name}: {data}")

            community_icon = data.get("data", {}).get("community_icon", default_icon)
            parsed_url = urlparse(community_icon)
            sanitized_url = urlunparse(parsed_url._replace(query=""))
            logger.info(f"Successfully fetched details for r/{subreddit_name}: Icon={sanitized_url}")

            return {
                "name": data.get("data", {}).get("display_name_prefixed", f"r/{subreddit_name}"),
                "icon": sanitized_url
            }
    except Exception as e:
        logger.error(f"Error fetching details for r/{subreddit_name}: {e}")
        return {"name": f"r/{subreddit_name}", "icon": default_icon}



async def fetch_reddit_posts(subreddit_name, last_post_id=None):
    try:
        reddit = await initialize_reddit_client()
        subreddit = await reddit.subreddit(subreddit_name, fetch=True)

        logger.info(f"Fetching new posts for r/{subreddit_name}")
        await subreddit.load()

        posts = []
        async for post in subreddit.new(limit=10):
            if last_post_id and post.id == last_post_id:
                logger.debug(f"Reached last processed post {last_post_id} in r/{subreddit_name}.")
                break
            posts.append(post)

        logger.info(f"Fetched {len(posts)} new posts for r/{subreddit_name}.")
        return posts
    except ResponseException as e:
        logger.error(f"Response error for r/{subreddit_name}: {e}")
    except NotFound:
        logger.error(f"Subreddit r/{subreddit_name} not found.")
    except Exception as e:
        logger.error(f"Error fetching posts for r/{subreddit_name}: {e}")
    finally:
        await reddit.close()
    return []


async def get_or_create_webhook(channel, subreddit_name=None, bot_name=None, bot_avatar=None):
    """Get or create a webhook for a channel."""
    try:
        if subreddit_name and (not bot_name or not bot_avatar):
            subreddit_details = await fetch_subreddit_details(subreddit_name)
            bot_name = bot_name or subreddit_details["name"]
            bot_avatar = bot_avatar or subreddit_details["icon"]

        if isinstance(bot_avatar, str) and bot_avatar.startswith("http"):
            async with http_session.get(bot_avatar) as response:
                bot_avatar = await response.read()

        webhooks = await channel.webhooks()
        webhook = next((wh for wh in webhooks if wh.user == bot.user), None)

        if webhook:
            await webhook.edit(name=bot_name, avatar=bot_avatar)
        else:
            webhook = await channel.create_webhook(name=bot_name, avatar=bot_avatar)

        await update_channel_config(str(channel.id), {"webhook_url": webhook.url})
        return webhook.url
    except discord.errors.Forbidden:
        logger.error(f"Bot lacks permissions to create/edit webhooks in {channel.name}.")
    except Exception as e:
        logger.error(f"Failed to get or create webhook for {channel.name}: {e}")
    return None

### Discord Slash Commands ###
@tree.command(name="subscribe", description="Subscribe a channel to a subreddit.")
@app_commands.describe(subreddit="The subreddit to subscribe to", channel="The channel to post updates in")
async def subscribe(interaction: discord.Interaction, subreddit: str, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    try:
        subreddit_details = await fetch_subreddit_details(subreddit)
        bot_name = subreddit_details["name"]
        bot_avatar = subreddit_details["icon"]

        # Get or create the webhook
        webhook_url = await get_or_create_webhook(channel, subreddit, bot_name, bot_avatar)
        if not webhook_url:
            await interaction.followup.send(f"Failed to create webhook for {channel.mention}. Check permissions or try again.", ephemeral=True)
            return

        # Update Firestore without last_post_id or last_post_timestamp
        data = {
            "subreddit": subreddit,
            "channel_id": str(channel.id),
            "webhook_url": webhook_url,
            "bot_name": bot_name,
            "bot_avatar": bot_avatar,
        }
        await update_channel_config(str(channel.id), data)

        await interaction.followup.send(f"Subscribed to updates from r/{subreddit} in {channel.mention}!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to subscribe: {e}", ephemeral=True)
        logger.error(f"Error in subscribe command: {e}")

@tree.command(name="unsubscribe", description="Unsubscribe a channel from a subreddit.")
async def unsubscribe(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    Unsubscribes a Discord channel from a subreddit by removing the corresponding configuration
    in Firestore and the associated sent_post_ids document.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        # Delete from `channel_configs`
        channel_id = str(channel.id)
        firestore_client.collection("channel_configs").document(channel_id).delete()
        logger.info(f"Deleted channel configuration for channel {channel_id}.")

        # Delete from `sent_post_ids`
        sent_post_ref = firestore_client.collection("sent_post_ids").document(channel_id)
        if sent_post_ref.get().exists:  # Check if the document exists before deleting
            sent_post_ref.delete()
            logger.info(f"Deleted sent_post_ids for channel {channel_id}.")
        else:
            logger.info(f"No sent_post_ids found for channel {channel_id} to delete.")

        await interaction.followup.send(f"Unsubscribed {channel.mention} successfully!", ephemeral=True)
    except Exception as e:
        logger.error(f"Error during unsubscribe for channel {channel.id}: {e}")
        await interaction.followup.send(f"Failed to unsubscribe {channel.mention}: {e}", ephemeral=True)



@tree.command(name="change_avatar", description="Change the bot's avatar for a specific channel")
@app_commands.describe(channel="The channel to update the avatar for", image_url="URL of the new avatar image")
async def change_avatar(interaction: discord.Interaction, channel: discord.TextChannel, image_url: str):
    try:
        # Acknowledge the interaction early
        await interaction.response.defer(ephemeral=True)

        # Update Firestore with the new avatar
        await update_channel_config(str(channel.id), {"bot_avatar": image_url})

        # Refresh the cache
        await reload_channel_config(str(channel.id))

        # Re-create or edit the webhook with the updated avatar
        bot_name = channel_configs.get(str(channel.id), {}).get("bot_name", bot.user.name)
        await get_or_create_webhook(channel, bot_name, image_url)

        # Send a follow-up response
        await interaction.followup.send(f"Avatar updated for `{channel.name}`!", ephemeral=True)
    except Exception as e:
        # Handle errors and send a follow-up response
        logger.error(f"Error in change_avatar command: {e}")
        await interaction.followup.send(f"Error changing avatar: {e}", ephemeral=True)



@tree.command(name="change_name", description="Change the bot's name for a specific channel")
@app_commands.describe(channel="The channel to update the name for", name="The new name for the bot")
async def change_name(interaction: discord.Interaction, channel: discord.TextChannel, name: str):
    try:
        await interaction.response.defer(ephemeral=True)  # Defer the response

        # Update Firestore
        await update_channel_config(str(channel.id), {"bot_name": name})

        # Refresh cache and recreate the webhook
        avatar_url = channel_configs.get(str(channel.id), {}).get("bot_avatar", None)
        webhook_url = await get_or_create_webhook(channel, None, name, avatar_url)

        if not webhook_url:
            await interaction.followup.send(f"Failed to update name for `{channel.name}`. Check permissions or try again.", ephemeral=True)
            return

        await interaction.followup.send(f"Name updated to `{name}` for `{channel.name}`!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error changing name: {e}", ephemeral=True)
        logger.error(f"Error in change_name command: {e}")

### Periodic Reddit Fetch Task ###
# Helper: Send message via webhook
async def send_message_with_webhook(webhook_url, content=None, embeds=None, username=None, avatar_url=None, post_link=None):
    """
    Sends a message to a Discord webhook.
    """
    try:
        payload = {
            "content": content,
            "embeds": [embed.to_dict() for embed in embeds] if embeds else None,
            "username": username,
            "avatar_url": avatar_url,
            "components": [
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
            ] if post_link else None,
        }

        async with http_session.post(webhook_url, json=payload) as response:
            if response.status in {200, 204}:
                logging.info(f"Message sent successfully via webhook to {webhook_url}")
            else:
                logging.error(f"Failed to send message. Status: {response.status}, Body: {await response.text()}")
    except Exception as e:
        logging.error(f"Error sending message with webhook: {e}")

# Helper: Create embeds
async def create_embeds(post, subreddit_name, media_urls):
    """
    Creates Discord embeds for a Reddit post.
    """
    author_avatar = await fetch_reddit_avatar(post.author.name) if post.author else \
        "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"

    embeds = []

    if media_urls:  # If there are images or media
        for image_url in media_urls[:4]:  # Limit to 4 images
            embed = discord.Embed(
                title=post.title,
                url=f"https://www.reddit.com{post.permalink}",
                color=discord.Color.blue()
            )
            embed.set_author(name=f"u/{post.author.name}" if post.author else "Anonymous", icon_url=author_avatar)
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Subreddit: r/{subreddit_name}")
            embeds.append(embed)
    elif post.selftext:  # If the post has text content (selftext)
        embed = discord.Embed(
            title=post.title,
            url=f"https://www.reddit.com{post.permalink}",
            description=post.selftext[:2048],  # Discord embed limit for description
            color=discord.Color.blue()
        )
        embed.set_author(name=f"u/{post.author.name}" if post.author else "Anonymous", icon_url=author_avatar)
        embed.set_footer(text=f"Subreddit: r/{subreddit_name}")
        embeds.append(embed)
    else:  # Fallback for unsupported or empty content
        embed = discord.Embed(
            title=post.title,
            url=f"https://www.reddit.com{post.permalink}",
            color=discord.Color.blue()
        )
        embed.set_author(name=f"u/{post.author.name}" if post.author else "Anonymous", icon_url=author_avatar)
        embed.set_footer(text=f"Subreddit: r/{subreddit_name}")
        embeds.append(embed)

    return embeds

# Helper: Fetch Reddit avatar
async def fetch_reddit_avatar(username):
    """
    Fetches the Reddit avatar for the post author.
    """
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

# Task: Fetch Reddit posts and post them to Discord
@tasks.loop(minutes=1)
async def fetch_reddit_and_post():
    """
    Periodically fetches the latest Reddit posts and posts them to Discord.
    """
    logger.info("Starting fetch task for all subscribed subreddits.")
    try:
        configs = firestore_client.collection("channel_configs").stream()
        for config in configs:
            data = config.to_dict()
            subreddit_name = data.get("subreddit")
            channel_id = data.get("channel_id")
            webhook_url = data.get("webhook_url")
            last_post_timestamp = float(data.get("last_post_timestamp", 0))

            if not subreddit_name or not webhook_url:
                logger.warning(f"Skipping channel {channel_id}: Missing subreddit or webhook URL.")
                continue

            try:
                logger.info(f"Processing subreddit r/{subreddit_name} for channel {channel_id}.")

                # Initialize Reddit client and load subreddit details
                reddit = await initialize_reddit_client()
                subreddit = await reddit.subreddit(subreddit_name)
                await subreddit.load()

                # Fetch subreddit details if missing
                if not data.get("bot_name") or not data.get("bot_avatar"):
                    subreddit_details = await fetch_subreddit_details(subreddit_name)
                    data["bot_name"] = subreddit_details["name"]
                    data["bot_avatar"] = subreddit_details["icon"]
                    await update_channel_config(channel_id, data)
                    logger.info(f"Updated subreddit details for r/{subreddit_name}: {subreddit_details}")

                bot_name = data.get("bot_name", "DefaultBot")
                bot_avatar = data.get(
                    "bot_avatar",
                    "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"
                )

                # Fetch new posts
                new_posts = []
                async for post in subreddit.new(limit=50):
                    if float(post.created_utc) > last_post_timestamp:
                        new_posts.append(post)

                if not new_posts:
                    logger.info(f"No new posts found for r/{subreddit_name}.")
                    continue

                new_posts.reverse()  # Process from oldest to newest
                logger.info(f"Found {len(new_posts)} new posts for r/{subreddit_name}.")

                for post in new_posts:
                    logger.debug(f"Processing post {post.id} from r/{subreddit_name}.")

                    # Skip duplicates
                    if await is_duplicate_post(channel_id, post.id):
                        logger.info(f"Post {post.id} already processed for channel {channel_id}. Skipping.")
                        continue

                    # Process media
                    media_urls = []
                    try:
                        if hasattr(post, "gallery_data") and hasattr(post, "media_metadata"):
                            for media_item in post.gallery_data.get("items", []):
                                media_id = media_item.get("media_id")
                                if media_id and media_id in post.media_metadata:
                                    media_data = post.media_metadata[media_id]
                                    media_url = media_data.get("s", {}).get("u")
                                    if media_url:
                                        media_urls.append(media_url)
                        elif post.url and post.url.endswith(('.jpg', '.png', '.gif')):
                            media_urls.append(post.url)
                        elif hasattr(post, "preview") and isinstance(post.preview, dict):
                            preview_images = post.preview.get("images", [])
                            if preview_images:
                                media_url = preview_images[0].get("source", {}).get("url")
                                if media_url:
                                    media_urls.append(media_url)

                        if not media_urls:
                            logger.warning(f"No media found for post {post.id} in r/{subreddit_name}.")
                    except (KeyError, AttributeError) as e:
                        logger.warning(f"Error while processing media for post {post.id}: {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error processing media for post {post.id}: {e}")
                        continue

                    # Create embeds and send to Discord
                    embeds = await create_embeds(post, subreddit_name, media_urls)
                    await send_message_with_webhook(
                        webhook_url=webhook_url,
                        embeds=embeds,
                        username=bot_name,
                        avatar_url=bot_avatar,
                        post_link=f"https://www.reddit.com{post.permalink}"
                    )

                    # Update sent_post_ids and Firestore
                    await add_to_sent_post_ids(channel_id, post.id)
                    firestore_client.collection("channel_configs").document(config.id).update({
                        "last_post_id": post.id,
                        "last_post_timestamp": post.created_utc
                    })
                    logger.info(f"Updated last_post_id ({post.id}) and last_post_timestamp ({post.created_utc}) for channel {channel_id}.")

            except Exception as e:
                logger.error(f"Error processing subreddit r/{subreddit_name} for channel {channel_id}: {e}")

    except Exception as e:
        logger.error(f"Error in fetch_reddit_and_post task: {e}")



async def is_duplicate_post(channel_id, post_id):
    """
    Check if a post ID already exists in sent_post_ids for the given channel.
    """
    try:
        sent_posts_ref = firestore_client.collection("sent_post_ids").document(channel_id).collection("posts")
        docs = sent_posts_ref.stream()
        for doc in docs:
            if post_id in doc.to_dict().get("post_ids", []):
                return True
        return False
    except Exception as e:
        logging.error(f"Error checking duplicate posts for channel {channel_id}: {e}")
        return True


async def add_to_sent_post_ids(channel_id, post_id):
    """
    Add a post ID to the sent_post_ids collection for the channel.
    Keep only the last 50 IDs to avoid exceeding Firestore limits.
    """
    try:
        sent_post_ref = firestore_client.collection("sent_post_ids").document(channel_id)
        sent_post_data = sent_post_ref.get().to_dict() if sent_post_ref.get().exists else {"post_ids": []}

        if post_id not in sent_post_data["post_ids"]:
            sent_post_data["post_ids"].append(post_id)

        # Keep only the last 50 post IDs
        sent_post_data["post_ids"] = sent_post_data["post_ids"][-50:]

        sent_post_ref.set(sent_post_data)
        logging.info(f"Added post {post_id} to sent_post_ids for channel {channel_id}.")
    except Exception as e:
        logging.error(f"Failed to update sent_post_ids for channel {channel_id}: {e}")



### Bot Events ###

@bot.event
async def on_ready():
    await initialize_http_session()
    await initialize_reddit_client()
    await load_channel_configs()
    fetch_reddit_and_post.start()
    await bot.tree.sync()
    logger.info(f"Logged in as {bot.user}.")

@bot.event
async def on_close():
    if http_session and not http_session.closed:
        await http_session.close()
    logger.info("Bot shutting down.")

### Main Entry Point ###

async def main():
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")