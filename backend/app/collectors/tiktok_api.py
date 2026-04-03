import logging
import httpx
from datetime import datetime, timezone
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)

class TikTokBusinessAPI:
    """
    Collector for TikTok Business API metrics.
    Handles rate limiting, fetching metrics, and returning structured data.
    """
    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or settings.tiktok_access_token
        self.base_url = "https://business-api.tiktok.com/open_api/v1.3"
        
    async def fetch_video_metrics(self, video_id: str) -> dict | None:
        """
        Fetches metrics for a specific video id.
        """
        if not self.access_token:
            logger.warning("TikTok access token missing. Skipping fetch.")
            return None
            
        url = f"{self.base_url}/video/metrics/"
        headers = {
            "Access-Token": self.access_token,
            "Content-Type": "application/json"
        }
        params = {
            "video_id": video_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                
            if response.status_code == 429:
                logger.warning("Rate limit hit on TikTok API")
                return None
                
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                logger.error(f"TikTok API error: {data.get('message')}")
                return None
                
            metrics = data.get("data", {})
            return {
                "views": metrics.get("view_count", 0),
                "likes": metrics.get("like_count", 0),
                "comments": metrics.get("comment_count", 0),
                "shares": metrics.get("share_count", 0),
                "saves": metrics.get("collect_count", 0),
                "avg_watch_time": metrics.get("avg_watch_time", 0.0),
                "play_count": metrics.get("play_count", 0)
            }
        except Exception as e:
            logger.error(f"Failed to fetch TikTok metrics for {video_id}: {str(e)}")
            return None
