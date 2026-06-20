# core/folder_manager.py

import os
import requests
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class FolderManager:
    """Manages folder creation and media organization"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.movies_path = config_manager.get('paths.movies', 'media/movies')
        self.tv_path = config_manager.get('paths.tv_shows', 'media/tv')
    
    def create_movie_folder(self, title: str, year: int = None) -> Optional[str]:
        """Create a folder for a movie"""
        folder_name = f"{title} ({year})" if year else title
        folder_name = self._sanitize_filename(folder_name)
        folder_path = os.path.join(self.movies_path, folder_name)
        
        try:
            os.makedirs(folder_path, exist_ok=True)
            logger.info(f"Created movie folder: {folder_path}")
            return folder_path
        except Exception as e:
            logger.error(f"Failed to create movie folder: {e}")
            return None
    
    def create_series_folder(self, title: str, year: int = None) -> Optional[str]:
        """Create a folder for a TV series"""
        folder_name = f"{title} ({year})" if year else title
        folder_name = self._sanitize_filename(folder_name)
        folder_path = os.path.join(self.tv_path, folder_name)
        
        try:
            os.makedirs(folder_path, exist_ok=True)
            logger.info(f"Created series folder: {folder_path}")
            return folder_path
        except Exception as e:
            logger.error(f"Failed to create series folder: {e}")
            return None
    
    def create_season_folder(self, series_path: str, season_num: int) -> Optional[str]:
        """Create a season folder within a series folder"""
        season_folder_name = f"Season {season_num:02d}"
        season_path = os.path.join(series_path, season_folder_name)
        
        try:
            os.makedirs(season_path, exist_ok=True)
            logger.info(f"Created season folder: {season_path}")
            return season_path
        except Exception as e:
            logger.error(f"Failed to create season folder: {e}")
            return None
    
    def save_poster(self, folder_path: str, poster_url: str) -> Optional[str]:
        """Download and save poster to folder"""
        if not poster_url:
            logger.warning("No poster URL provided")
            return None
            
        # Determine file extension from URL or default to .jpg
        if '.jpg' in poster_url.lower() or '.jpeg' in poster_url.lower():
            ext = '.jpg'
        elif '.png' in poster_url.lower():
            ext = '.png'
        elif '.webp' in poster_url.lower():
            ext = '.webp'
        else:
            ext = '.jpg'
        
        poster_path = os.path.join(folder_path, f'poster{ext}')
        
        try:
            # Download the image
            response = requests.get(poster_url, timeout=15)
            if response.status_code == 200:
                with open(poster_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded poster to: {poster_path}")
                return poster_path
            else:
                logger.warning(f"Failed to download poster: HTTP {response.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.error(f"Timeout downloading poster from {poster_url}")
            return None
        except Exception as e:
            logger.error(f"Failed to save poster: {e}")
            return None
    
    def save_backdrop(self, folder_path: str, backdrop_url: str) -> Optional[str]:
        """Download and save backdrop to folder"""
        if not backdrop_url:
            return None
            
        # Determine file extension
        if '.jpg' in backdrop_url.lower() or '.jpeg' in backdrop_url.lower():
            ext = '.jpg'
        elif '.png' in backdrop_url.lower():
            ext = '.png'
        else:
            ext = '.jpg'
        
        backdrop_path = os.path.join(folder_path, f'backdrop{ext}')
        
        try:
            response = requests.get(backdrop_url, timeout=15)
            if response.status_code == 200:
                with open(backdrop_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded backdrop to: {backdrop_path}")
                return backdrop_path
            else:
                logger.warning(f"Failed to download backdrop: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Failed to save backdrop: {e}")
            return None
    
    def _sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        # Also remove trailing spaces and dots
        filename = filename.strip().rstrip('.')
        return filename