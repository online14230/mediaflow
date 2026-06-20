# core/metadata_provider.py

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MetadataProvider:
    def __init__(self, config: Dict):
        self.api_key = config.get('api_key', '')
        self.base_url = "https://api.themoviedb.org/3"
        self.timeout = 5
    
    def search_movies(self, query: str) -> List[Dict]:
        results = []
        if self.api_key:
            try:
                url = f"{self.base_url}/search/movie"
                params = {'api_key': self.api_key, 'query': query}
                response = requests.get(url, params=params, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    for movie in data.get('results', [])[:10]:
                        results.append({
                            'id': movie.get('id'),
                            'title': movie.get('title'),
                            'year': movie.get('release_date', '')[:4],
                            'overview': movie.get('overview', ''),
                            'poster_path': movie.get('poster_path'),
                            'rating': movie.get('vote_average')
                        })
            except Exception as e:
                logger.error(f"Search error: {e}")
        
        if not results:
            results = [{'id': 1, 'title': f'{query}', 'year': None, 'overview': 'Add TMDB API key in settings for real results'}]
        return results
    
    def search_tv_series(self, query: str) -> List[Dict]:
        results = []
        if self.api_key:
            try:
                url = f"{self.base_url}/search/tv"
                params = {'api_key': self.api_key, 'query': query}
                response = requests.get(url, params=params, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    for series in data.get('results', [])[:10]:
                        results.append({
                            'id': series.get('id'),
                            'title': series.get('name'),
                            'year': series.get('first_air_date', '')[:4],
                            'overview': series.get('overview', ''),
                            'poster_path': series.get('poster_path'),
                            'rating': series.get('vote_average')
                        })
            except Exception as e:
                logger.error(f"Search error: {e}")
        
        if not results:
            results = [{'id': 100, 'title': f'{query}', 'year': None, 'overview': 'Add TMDB API key in settings for real results'}]
        return results
    
    def get_movie_details(self, movie_id: int) -> Optional[Dict]:
        if not self.api_key:
            return None
        try:
            url = f"{self.base_url}/movie/{movie_id}"
            response = requests.get(url, params={'api_key': self.api_key}, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return {
                    'id': data.get('id'),
                    'title': data.get('title'),
                    'year': data.get('release_date', '')[:4],
                    'overview': data.get('overview', ''),
                    'poster_path': data.get('poster_path'),
                    'runtime': data.get('runtime'),
                    'rating': data.get('vote_average')
                }
        except Exception as e:
            logger.error(f"Details error: {e}")
        return None
    
    def get_series_details(self, series_id: int) -> Optional[Dict]:
        """Get TV series details"""
        if not self.api_key:
            return {
                'id': series_id,
                'title': 'Example Series',
                'year': 2024,
                'overview': 'Add TMDB API key in settings for real metadata',
                'poster_path': None,
                'rating': 0
            }
        try:
            url = f"{self.base_url}/tv/{series_id}"
            response = requests.get(url, params={'api_key': self.api_key}, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return {
                    'id': data.get('id'),
                    'title': data.get('name'),
                    'year': data.get('first_air_date', '')[:4],
                    'overview': data.get('overview', ''),
                    'poster_path': data.get('poster_path'),
                    'rating': data.get('vote_average')
                }
        except Exception as e:
            logger.error(f"Series details error: {e}")
        return None
    
    def get_upcoming_releases(self, days: int = 30) -> List[Dict]:
        """Get upcoming releases - returns empty list if no API key"""
        if not self.api_key:
            return []  # Return empty list instead of mock data
        try:
            # This would call a real API in production
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error getting upcoming releases: {e}")
            return []