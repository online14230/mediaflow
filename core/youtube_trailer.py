# core/youtube_trailer.py - Fetch YouTube trailers

import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class YouTubeTrailerFetcher:
    """Fetch YouTube trailers for movies and TV shows"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.youtube_api_key = config_manager.get('youtube_api_key', '')
        self.cache = {}
    
    def search_trailer(self, title: str, year: int = None, media_type: str = 'movie') -> List[Dict]:
        """Search for trailers on YouTube"""
        cache_key = f"{title}_{year}_{media_type}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        results = []
        
        # Build search query
        query = f"{title} "
        if media_type == 'movie':
            query += "movie trailer"
        else:
            query += "tv series trailer"
        if year:
            query += f" {year}"
        
        # If YouTube API key is available, use it
        if self.youtube_api_key:
            results = self._search_with_api(query)
        else:
            # Fallback to mock data
            results = self._mock_trailer_results(title, year)
        
        self.cache[cache_key] = results
        return results
    
    def _search_with_api(self, query: str) -> List[Dict]:
        """Search using YouTube Data API"""
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': 5,
                'key': self.youtube_api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('items', []):
                    results.append({
                        'id': item['id']['videoId'],
                        'title': item['snippet']['title'],
                        'thumbnail': item['snippet']['thumbnails']['medium']['url'],
                        'embed_url': f"https://www.youtube.com/embed/{item['id']['videoId']}"
                    })
                return results
        except Exception as e:
            logger.error(f"YouTube API error: {e}")
        return []
    
    def _mock_trailer_results(self, title: str, year: int = None) -> List[Dict]:
        """Return mock trailer data when API key is not available"""
        return [
            {
                'id': 'dQw4w9WgXcQ',
                'title': f'{title} Official Trailer',
                'thumbnail': 'https://img.youtube.com/vi/dQw4w9WgXcQ/mqdefault.jpg',
                'embed_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ'
            }
        ]
    
    def get_trailer_embed(self, video_id: str) -> str:
        """Get embed HTML for a YouTube video"""
        return f'<iframe width="100%" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'