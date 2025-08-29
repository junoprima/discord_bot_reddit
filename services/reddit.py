import asyncio
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, urlunparse
import aiohttp
import asyncpraw
from asyncprawcore.exceptions import ResponseException, NotFound
from config.settings import get_settings

logger = logging.getLogger(__name__)

class RedditService:
    """Reddit API service for fetching subreddit data and posts"""
    
    def __init__(self):
        self.settings = get_settings()
        self.reddit_client: Optional[asyncpraw.Reddit] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """Initialize Reddit client and HTTP session"""
        if not self.reddit_client:
            self.reddit_client = asyncpraw.Reddit(
                client_id=self.settings.reddit_client_id,
                client_secret=self.settings.reddit_client_secret,
                user_agent=self.settings.reddit_user_agent
            )
        
        if not self.http_session:
            self.http_session = aiohttp.ClientSession()
    
    async def cleanup(self):
        """Clean up resources"""
        if self.reddit_client:
            await self.reddit_client.close()
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
    
    async def fetch_subreddit_details(self, subreddit_name: str) -> Dict[str, str]:
        """Fetch subreddit details including icon and display name"""
        default_icon = "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"
        
        try:
            await self.initialize()
            
            url = f"https://www.reddit.com/r/{subreddit_name}/about.json"
            headers = {"User-Agent": self.settings.reddit_user_agent}
            
            logger.info(f"Fetching subreddit details for r/{subreddit_name}")
            
            async with self.http_session.get(url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch details for r/{subreddit_name} (HTTP {response.status}): {error_text}")
                    return {"name": f"r/{subreddit_name}", "icon": default_icon}
                
                data = await response.json()
                community_icon = data.get("data", {}).get("community_icon", default_icon)
                
                # Clean URL parameters
                parsed_url = urlparse(community_icon)
                sanitized_url = urlunparse(parsed_url._replace(query=""))
                
                logger.info(f"Successfully fetched details for r/{subreddit_name}")
                
                return {
                    "name": data.get("data", {}).get("display_name_prefixed", f"r/{subreddit_name}"),
                    "icon": sanitized_url
                }
                
        except Exception as e:
            logger.error(f"Error fetching details for r/{subreddit_name}: {e}")
            return {"name": f"r/{subreddit_name}", "icon": default_icon}
    
    async def fetch_reddit_posts(self, subreddit_name: str, last_post_timestamp: float = 0) -> List[Any]:
        """Fetch new Reddit posts from subreddit"""
        try:
            await self.initialize()
            subreddit = await self.reddit_client.subreddit(subreddit_name, fetch=True)
            await subreddit.load()
            
            logger.info(f"Fetching new posts for r/{subreddit_name}")
            
            new_posts = []
            async for post in subreddit.new(limit=self.settings.max_posts_per_fetch):
                if float(post.created_utc) > last_post_timestamp:
                    new_posts.append(post)
                await asyncio.sleep(0.5)  # Rate limiting
            
            new_posts.reverse()  # Process oldest first
            logger.info(f"Fetched {len(new_posts)} new posts for r/{subreddit_name}")
            return new_posts
            
        except ResponseException as e:
            logger.error(f"Response error for r/{subreddit_name}: {e}")
        except NotFound:
            logger.error(f"Subreddit r/{subreddit_name} not found")
        except Exception as e:
            logger.error(f"Error fetching posts for r/{subreddit_name}: {e}")
        
        return []
    
    async def fetch_user_avatar(self, username: str) -> str:
        """Fetch Reddit user avatar"""
        default_avatar = "https://www.redditstatic.com/avatars/avatar_default_02_46A508.png"
        
        try:
            await self.initialize()
            user = await self.reddit_client.redditor(username, fetch=True)
            avatar_url = getattr(user, "icon_img", default_avatar)
            return avatar_url.split('?')[0]  # Clean URL
        except Exception as e:
            logger.error(f"Error fetching avatar for {username}: {e}")
            return default_avatar
    
    async def extract_media_urls(self, post) -> List[str]:
        """Extract media URLs from Reddit post"""
        media_urls = []
        
        try:
            # Handle gallery posts
            if hasattr(post, "gallery_data") and hasattr(post, "media_metadata"):
                for media_item in post.gallery_data.get("items", []):
                    media_id = media_item.get("media_id")
                    if media_id and media_id in post.media_metadata:
                        media_data = post.media_metadata[media_id]
                        media_url = media_data.get("s", {}).get("u")
                        if media_url:
                            media_urls.append(media_url)
            
            # Handle direct image links
            elif post.url and post.url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                media_urls.append(post.url)
            
            # Handle preview images
            elif hasattr(post, "preview") and isinstance(post.preview, dict):
                preview_images = post.preview.get("images", [])
                if preview_images:
                    media_url = preview_images[0].get("source", {}).get("url")
                    if media_url:
                        media_urls.append(media_url)
                        
        except Exception as e:
            logger.warning(f"Error extracting media from post {post.id}: {e}")
        
        return media_urls