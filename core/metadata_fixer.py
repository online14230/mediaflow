# core/metadata_fixer.py - Complete with NFO support

import requests
import logging
from typing import List, Dict, Optional
import os
from pathlib import Path
from datetime import datetime

from core.nfo_parser import NFOParser

logger = logging.getLogger(__name__)

class MetadataFixer:
    """Fix missing metadata for movies and TV series using TMDB and NFO files"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.tmdb_api_key = config_manager.get('metadata.providers.tmdb.api_key', '')
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p"
        self.nfo_parser = NFOParser()
    
    def import_from_nfo(self, folder_path: str, media_type: str = 'movie') -> Optional[Dict]:
        """Import metadata from NFO file in folder"""
        nfo_path = self.nfo_parser.find_nfo_file(folder_path, media_type)
        if not nfo_path:
            logger.warning(f"No NFO file found in {folder_path}")
            return None
        
        if media_type == 'movie':
            return self.nfo_parser.parse_movie_nfo(nfo_path)
        else:
            return self.nfo_parser.parse_tv_nfo(nfo_path)
    
    def export_to_nfo(self, folder_path: str, metadata: Dict, media_type: str = 'movie') -> bool:
        """Export metadata to NFO file in folder"""
        if media_type == 'movie':
            nfo_path = os.path.join(folder_path, 'movie.nfo')
            return self.nfo_parser.write_movie_nfo(nfo_path, metadata)
        else:
            nfo_path = os.path.join(folder_path, 'tvshow.nfo')
            logger.warning("TV show NFO export not yet implemented")
            return False
    
    def search_movie(self, title: str, year: int = None) -> List[Dict]:
        """Search for a movie by title"""
        if not self.tmdb_api_key:
            logger.warning("No TMDB API key configured")
            return []
        
        try:
            url = f"{self.base_url}/search/movie"
            params = {
                'api_key': self.tmdb_api_key,
                'query': title,
                'language': 'en-US'
            }
            if year:
                params['year'] = year
                
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = []
                for movie in data.get('results', [])[:10]:
                    results.append({
                        'id': movie.get('id'),
                        'title': movie.get('title'),
                        'year': movie.get('release_date', '')[:4] if movie.get('release_date') else None,
                        'overview': movie.get('overview', ''),
                        'poster_path': movie.get('poster_path'),
                        'backdrop_path': movie.get('backdrop_path'),
                        'rating': movie.get('vote_average'),
                        'release_date': movie.get('release_date')
                    })
                return results
            else:
                logger.error(f"TMDB API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Movie search error: {e}")
            return []
    
    def search_tv_series(self, title: str, year: int = None) -> List[Dict]:
        """Search for a TV series by title"""
        if not self.tmdb_api_key:
            logger.warning("No TMDB API key configured")
            return []
        
        try:
            url = f"{self.base_url}/search/tv"
            params = {
                'api_key': self.tmdb_api_key,
                'query': title,
                'language': 'en-US'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = []
                for series in data.get('results', [])[:10]:
                    results.append({
                        'id': series.get('id'),
                        'title': series.get('name'),
                        'year': series.get('first_air_date', '')[:4] if series.get('first_air_date') else None,
                        'overview': series.get('overview', ''),
                        'poster_path': series.get('poster_path'),
                        'backdrop_path': series.get('backdrop_path'),
                        'rating': series.get('vote_average'),
                        'first_air_date': series.get('first_air_date')
                    })
                return results
            else:
                logger.error(f"TMDB API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"TV search error: {e}")
            return []
    
    def get_movie_details(self, movie_id: int) -> Optional[Dict]:
        """Get detailed movie metadata"""
        if not self.tmdb_api_key:
            return None
        
        try:
            url = f"{self.base_url}/movie/{movie_id}"
            params = {
                'api_key': self.tmdb_api_key,
                'language': 'en-US',
                'append_to_response': 'credits,keywords'
            }
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                credits = data.get('credits', {})
                return {
                    'title': data.get('title'),
                    'year': data.get('release_date', '')[:4] if data.get('release_date') else None,
                    'overview': data.get('overview', ''),
                    'poster_path': data.get('poster_path'),
                    'backdrop_path': data.get('backdrop_path'),
                    'rating': data.get('vote_average'),
                    'runtime': data.get('runtime'),
                    'genres': [g.get('name') for g in data.get('genres', [])],
                    'director': self._get_director(credits),
                    'cast': self._get_cast(credits),
                    'release_date': data.get('release_date')
                }
            else:
                logger.error(f"TMDB API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Get movie details error: {e}")
            return None
    
    def get_series_details(self, series_id: int) -> Optional[Dict]:
        """Get detailed TV series metadata"""
        if not self.tmdb_api_key:
            return None
        
        try:
            url = f"{self.base_url}/tv/{series_id}"
            params = {
                'api_key': self.tmdb_api_key,
                'language': 'en-US',
                'append_to_response': 'credits,keywords'
            }
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                credits = data.get('credits', {})
                return {
                    'title': data.get('name'),
                    'year': data.get('first_air_date', '')[:4] if data.get('first_air_date') else None,
                    'overview': data.get('overview', ''),
                    'poster_path': data.get('poster_path'),
                    'backdrop_path': data.get('backdrop_path'),
                    'rating': data.get('vote_average'),
                    'seasons': data.get('number_of_seasons', 0),
                    'episodes': data.get('number_of_episodes', 0),
                    'status': data.get('status'),
                    'network': data.get('networks', [{}])[0].get('name') if data.get('networks') else None,
                    'genres': [g.get('name') for g in data.get('genres', [])],
                    'cast': self._get_cast(credits),
                    'first_air_date': data.get('first_air_date'),
                    'last_air_date': data.get('last_air_date')
                }
            else:
                logger.error(f"TMDB API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Get series details error: {e}")
            return None
    
    def download_poster(self, poster_path: str, save_path: str) -> bool:
        """Download poster image to local path"""
        if not poster_path:
            return False
        
        url = f"{self.image_base_url}/w500{poster_path}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded poster to {save_path}")
                return True
            else:
                logger.warning(f"Failed to download poster: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to download poster: {e}")
            return False
    
    def download_backdrop(self, backdrop_path: str, save_path: str) -> bool:
        """Download backdrop image to local path"""
        if not backdrop_path:
            return False
        
        url = f"{self.image_base_url}/w1280{backdrop_path}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded backdrop to {save_path}")
                return True
            else:
                logger.warning(f"Failed to download backdrop: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to download backdrop: {e}")
            return False
    
    def _get_director(self, credits: Dict) -> str:
        """Extract director name from credits"""
        for crew in credits.get('crew', []):
            if crew.get('job') == 'Director':
                return crew.get('name', '')
        return ''
    
    def _get_cast(self, credits: Dict, limit: int = 10) -> List[str]:
        """Extract cast names from credits"""
        cast = []
        for actor in credits.get('cast', [])[:limit]:
            cast.append(actor.get('name', ''))
        return cast