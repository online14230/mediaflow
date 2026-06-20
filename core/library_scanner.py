# core/library_scanner.py - Updated with better series detection

import os
import re
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LibraryScanner:
    """Scan existing media library and import to database"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
    
    def scan_movies_folder(self, folder_path):
        """Scan a folder for movie files and return list of found movies"""
        movies = []
        
        if not os.path.exists(folder_path):
            return movies
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if Path(file).suffix.lower() in self.video_extensions:
                    movie_info = self._extract_movie_info(file, root)
                    if movie_info:
                        movies.append(movie_info)
        
        return movies
    
    def scan_tv_folder(self, folder_path):
        """Scan a folder for TV episode files - returns episodes grouped by potential series"""
        episodes = []
        
        if not os.path.exists(folder_path):
            return episodes
        
        # First, identify all series folders (folders that contain season subfolders or episodes)
        series_folders = self._identify_series_folders(folder_path)
        
        for series_folder in series_folders:
            # Get the base series name by cleaning the folder name
            series_name = os.path.basename(series_folder)
            # Remove season indicators like "S01", "Season 1", "720p" etc.
            clean_series_name = self._clean_series_name(series_name)
            # Extract TMDB ID from folder name if present
            tmdb_id = self._extract_tmdb_id_from_folder(series_name)
            
            logger.info(f"Processing series: {clean_series_name} (from folder: {series_name})")
            
            # Scan all episodes in this series folder
            for root, dirs, files in os.walk(series_folder):
                for file in files:
                    if Path(file).suffix.lower() in self.video_extensions:
                        episode_info = self._extract_tv_info(file, root, clean_series_name, tmdb_id)
                        if episode_info:
                            episodes.append(episode_info)
        
        return episodes
    
    def _identify_series_folders(self, base_path):
        """Identify all top-level series folders"""
        series_folders = []
        
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                # This is a potential series folder
                # Don't skip folders with "S01" in the name - they ARE series folders
                series_folders.append(item_path)
        
        return series_folders
    
    def _extract_tmdb_id_from_folder(self, folder_name):
        """Extract TMDB ID from folder name like 'Show Name (2019) [tmdbid-12345]'"""
        match = re.search(r'\[tmdbid[-\s]*(\d+)\]', folder_name, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def _clean_series_name(self, folder_name):
        """Clean series name by removing year, TMDB ID, and quality indicators"""
        # Remove [tmdbid-xxxx] pattern
        name = re.sub(r'\[tmdbid[-\s]*\d+\]', '', folder_name, flags=re.IGNORECASE)
        # Remove year pattern
        name = re.sub(r'\s*\(\d{4}\)\s*', ' ', name)
        # Remove quality indicators like 720p, 1080p, etc.
        name = re.sub(r'\s*\d{3,4}p\s*', ' ', name, flags=re.IGNORECASE)
        # Remove season indicators like S01, S02, Season 1, etc.
        name = re.sub(r'\s*[Ss]\d{1,2}\s*', ' ', name)
        name = re.sub(r'\s*[Ss]eason\s*\d{1,2}\s*', ' ', name, flags=re.IGNORECASE)
        # Clean up
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    def _extract_movie_info(self, filename, folder_path):
        """Extract movie title and year from filename"""
        name = Path(filename).stem
        
        patterns = [
            r'^(.+?)\s*\((\d{4})\)',
            r'^(.+?)\.(\d{4})',
            r'^(.+?)\s+(\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                title = match.group(1).replace('.', ' ').replace('_', ' ').strip()
                year = match.group(2)
                return {
                    'title': title,
                    'year': int(year),
                    'filename': filename,
                    'path': os.path.join(folder_path, filename),
                    'file_size': os.path.getsize(os.path.join(folder_path, filename))
                }
        
        title = name.replace('.', ' ').replace('_', ' ').strip()
        return {
            'title': title,
            'year': None,
            'filename': filename,
            'path': os.path.join(folder_path, filename),
            'file_size': os.path.getsize(os.path.join(folder_path, filename))
        }
    
    def _extract_tv_info(self, filename, folder_path, series_name, tmdb_id):
        """Extract TV show season and episode with improved pattern matching"""
        name = Path(filename).stem
        
        # Try to extract season and episode from filename
        season = None
        episode = None
        
        # Pattern 1: S01E01
        match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', name, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            logger.debug(f"Found S{season:02d}E{episode:02d} in filename: {filename}")
        
        # Pattern 2: 1x01
        if season is None:
            match = re.search(r'(\d{1,2})x(\d{1,3})', name, re.IGNORECASE)
            if match:
                season = int(match.group(1))
                episode = int(match.group(2))
                logger.debug(f"Found {season}x{episode} in filename: {filename}")
        
        # Pattern 3: Extract season from folder name
        if season is None:
            # Look for season in folder path
            path_parts = Path(folder_path).parts
            for part in path_parts:
                match = re.search(r'[Ss]eason\s*(\d{1,2})', part, re.IGNORECASE)
                if match:
                    season = int(match.group(1))
                    break
                match = re.search(r'[Ss](\d{1,2})$', part, re.IGNORECASE)
                if match:
                    season = int(match.group(1))
                    break
            
            # Try to find episode number from filename
            if season is not None:
                ep_match = re.search(r'[Ee](\d{1,3})', name, re.IGNORECASE)
                if ep_match:
                    episode = int(ep_match.group(1))
                else:
                    ep_match = re.search(r'(\d{1,3})$', name)
                    if ep_match:
                        episode = int(ep_match.group(1))
        
        if season is not None and episode is not None:
            return {
                'title': series_name,
                'season': season,
                'episode': episode,
                'tmdb_id': tmdb_id,
                'filename': filename,
                'path': os.path.join(folder_path, filename),
                'folder_path': folder_path,
                'file_size': os.path.getsize(os.path.join(folder_path, filename))
            }
        
        logger.warning(f"Could not extract season/episode from: {filename}")
        return None


class DuplicateDetector:
    """Detect and handle duplicate media entries"""
    
    @staticmethod
    def normalize_series_title(title: str) -> str:
        """Normalize series title for comparison"""
        if not title:
            return ""
        
        title = title.lower()
        title = re.sub(r'\s*\(\d{4}\)\s*', ' ', title)
        title = re.sub(r'\s*\d{3,4}p\s*', ' ', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*[Ss]\d{1,2}\s*', ' ', title)
        title = re.sub(r'\s*[Ss]eason\s*\d{1,2}\s*', ' ', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*\[tmdbid[-\s]*\d+\]\s*', ' ', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title
    
    @staticmethod
    def titles_match(title1: str, title2: str) -> bool:
        """Check if two titles match using enhanced normalization"""
        normalized1 = DuplicateDetector.normalize_series_title(title1)
        normalized2 = DuplicateDetector.normalize_series_title(title2)
        return normalized1 == normalized2