import asyncpraw
import discord
from discord.ext import commands, tasks
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
        logging.FileHandler("logs/reddit_feed_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Override aiohttp.ClientSession to track unintended creations
original_init = aiohttp.ClientSession.__init__

def new_init(self, *args, **kwargs):
    logger.error("A new aiohttp.ClientSession was created!")
    import traceback
    for line in traceback.format_stack():
        logger.debug(line.strip())
    original_init(self, *args, **kwargs)

aiohttp.ClientSession.__init__ = new_init

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

http_session = None  # Global aiohttp.ClientSession instance


# Helper: Send message via webhook
async def send_message_with_webhook(webhook_url, content=None, embeds=None, username=None, avatar_url=None, post_link=None):
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
                            "label": "Post Link",
                            "style": 5,  # Link button
                            "url": post_link,
                        }
                    ],
                }
            ] if post_link else None,
        }

        async with http_session.post(webhook_url, json=payload) as response:
            if response.status in {200, 204}:
                logger.info(f"Message sent successfully via webhook to {webhook_url}")
            else:
                logger.error(f"Failed to send message. Status: {response.status}, Body: {await response.text()}")
    except Exception as e:
        logger.error(f"Error sending message with webhook: {e}")


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

    if media_urls:  # If there are images or media
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
    elif post.selftext:  # If the post has text content (selftext)
        embed = discord.Embed(
            title=post.title,
            url=f"https://www.reddit.com{post.permalink}",
            description=post.selftext[:2048],  # Discord embed limit for description
            color=discord.Color.blue()
        )
        embed.set_author(name=f"{post.author.name}", icon_url=author_avatar)
        embed.set_footer(text=f"Subreddit: r/{subreddit_name}")
        embeds.append(embed)
    else:  # Fallback for unsupported or empty content
        embed = discord.Embed(
            title=post.title,
            url=f"https://www.reddit.com{post.permalink}",
            color=discord.Color.blue()
        )
        embed.set_author(name=f"{post.author.name}", icon_url=author_avatar)
        embed.set_footer(text=f"Subreddit: r/{subreddit_name}")
        embeds.append(embed)

    return embeds


# Task: Fetch Reddit posts and post them to Discord
@tasks.loop(minutes=1)
async def fetch_reddit_and_post():
    try:
        configs = firestore_client.collection("channel_configs").stream()
        for config in configs:
            data = config.to_dict()
            subreddit_name = data.get("subreddit")
            channel_id = data.get("channel_id")
            webhook_url = data.get("webhook_url")
            bot_name = data.get("bot_name", "DefaultBot")
            bot_avatar = data.get("bot_avatar", "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png")
            last_post_timestamp = data.get("last_post_timestamp", 0)  # Default to 0 if not set

            if not channel_id or not webhook_url:
                logger.warning(f"Channel ID or webhook URL is missing for subreddit {subreddit_name}.")
                continue

            # Initialize or fetch sent post IDs
            sent_post_ids_ref = firestore_client.collection("sent_post_ids").document(channel_id)
            sent_post_ids_doc = sent_post_ids_ref.get()
            sent_post_ids = sent_post_ids_doc.to_dict().get("post_ids", []) if sent_post_ids_doc.exists else []

            # Fetch the latest post from the subreddit
            reddit = asyncpraw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT,
                requestor=Requestor("aiohttp", session=http_session)
            )
            subreddit = await reddit.subreddit(subreddit_name)
            async for post in subreddit.new(limit=1):
                post_timestamp = int(post.created_utc)  # Timestamp of the post in UTC

                # Check if the post is already sent or if it's older
                if post.id in sent_post_ids or post_timestamp <= last_post_timestamp:
                    logger.info(f"Skipping post {post.id} for r/{subreddit_name} in channel {channel_id} (already sent or older).")
                    continue

                # Check if the post is deleted
                try:
                    # Accessing post.title will throw an exception if the post is deleted
                    _ = post.title
                except Exception as e:
                    logger.warning(f"Post {post.id} for r/{subreddit_name} is deleted. Skipping. Error: {e}")
                    continue

                # Update sent_post_ids and last_post_timestamp in Firestore
                sent_post_ids.append(post.id)
                sent_post_ids_ref.set({"post_ids": sent_post_ids}, merge=True)
                doc_ref = firestore_client.collection("channel_configs").document(config.id)
                doc_ref.update({"last_post_timestamp": post_timestamp})

                # Determine the post type and content
                media_urls = []
                if hasattr(post, "gallery_data"):  # Handle multi-image gallery posts
                    for media_item in post.gallery_data["items"]:
                        media_id = media_item["media_id"]
                        if media_id in post.media_metadata:
                            media_urls.append(post.media_metadata[media_id]["s"]["u"])
                elif post.url.endswith(('.jpg', '.png', '.gif')):  # Single image
                    media_urls.append(post.url)
                elif hasattr(post, "preview") and post.preview.get("images"):  # Preview image
                    media_urls.append(post.preview["images"][0]["source"]["url"])

                # Create embeds and send the post
                embeds = await create_embeds(post, subreddit_name, media_urls)

                if embeds:  # Send embeds if available
                    await send_message_with_webhook(
                        webhook_url=webhook_url,
                        embeds=embeds,
                        username=bot_name,
                        avatar_url=bot_avatar,
                        post_link=f"https://www.reddit.com{post.permalink}"
                    )
                else:  # Fallback to just sending the "Post Link" button
                    await send_message_with_webhook(
                        webhook_url=webhook_url,
                        content=None,
                        embeds=None,
                        username=bot_name,
                        avatar_url=bot_avatar,
                        post_link=f"https://www.reddit.com{post.permalink}"
                    )
                logger.info(f"Processed post {post.id} for r/{subreddit_name} in channel {channel_id}.")
                break  # Process only the latest post per channel
    except Exception as e:
        logger.error(f"Error in fetch_reddit_and_post: {e}")

async def test_firestore():
    try:
        docs = firestore_client.collection("channel_configs").stream()
        for doc in docs:
            print(doc.id, doc.to_dict())
        logger.info("Firestore integration test passed.")
    except Exception as e:
        logger.error(f"Error connecting to Firestore: {e}")
        raise

async def validate_webhook_in_firestore(channel_id: str):
    try:
        doc = firestore_client.collection("channel_configs").document(channel_id).get()
        if doc.exists:
            data = doc.to_dict()
            webhook_url = data.get("webhook_url")
            logger.info(f"Webhook for channel {channel_id}: {webhook_url}")
            return webhook_url
        else:
            logger.warning(f"No webhook found for channel {channel_id} in Firestore.")
            return None
    except Exception as e:
        logger.error(f"Error validating webhook in Firestore for channel {channel_id}: {e}")
        return None


@bot.event
async def on_ready():
    global http_session
    if http_session is None:
        http_session = aiohttp.ClientSession()  # Create a single session

    await test_firestore()  # Test Firestore connectivity
    logger.info(f"Logged in as {bot.user}")

    fetch_reddit_and_post.start()

    

@bot.event
async def on_close():
    global http_session
    if http_session is not None and not http_session.closed:
        await http_session.close()
        logger.info("HTTP session closed in on_close.")

# Main entry
async def main():
    global http_session
    if http_session is None:
        http_session = aiohttp.ClientSession()
    try:
        await bot.start(DISCORD_TOKEN)
    finally:
        if http_session and not http_session.closed:
            await http_session.close()
            logger.info("HTTP session closed.")


if __name__ == "__main__":
    asyncio.run(main())
