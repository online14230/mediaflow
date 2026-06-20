# core/media_player.py - Fixed poster detection

import os
import re
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class MediaPlayer:
    """Handles media playback and metadata management"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    
    def find_poster_in_folder(self, folder_path: str) -> Optional[str]:
        """Find any poster image in a folder"""
        folder = Path(folder_path)
        if not folder.exists():
            logger.debug(f"Folder does not exist: {folder_path}")
            return None
        
        # Common poster filenames (in order of preference)
        poster_names = [
            'poster.jpg', 'poster.jpeg', 'poster.png', 'poster.webp',
            'folder.jpg', 'folder.jpeg', 'folder.png',
            'cover.jpg', 'cover.jpeg', 'cover.png',
            'movie.jpg', 'movie.png',
            'fanart.jpg', 'fanart.jpeg',
            'backdrop.jpg', 'backdrop.jpeg',
            'thumb.jpg', 'thumb.jpeg'
        ]
        
        # Check for exact matches first
        for name in poster_names:
            poster_path = folder / name
            if poster_path.exists():
                logger.info(f"Found poster: {poster_path}")
                return str(poster_path)
        
        # Look for any image file (prefer smaller files as they're likely posters)
        images = []
        for ext in self.image_extensions:
            images.extend(folder.glob(f'*{ext}'))
        
        if images:
            # Sort by file size (smaller files are usually posters)
            images.sort(key=lambda x: x.stat().st_size)
            logger.info(f"Found image as poster: {images[0]}")
            return str(images[0])
        
        # Also check one level up (for movies in flat structure)
        parent_folder = folder.parent
        if parent_folder != folder:
            for name in poster_names:
                poster_path = parent_folder / name
                if poster_path.exists():
                    logger.info(f"Found poster in parent folder: {poster_path}")
                    return str(poster_path)
        
        logger.debug(f"No poster found in {folder_path}")
        return None
    
    def get_movie_files(self, movie_path: str) -> Dict:
        """Get all media files for a movie"""
        result = {
            'video': None,
            'poster': None,
            'backdrop': None,
            'subtitles': []
        }
        
        movie_dir = Path(movie_path)
        
        # If movie_path is a file, get its parent directory
        if movie_dir.is_file():
            movie_dir = movie_dir.parent
            result['video'] = movie_path
        else:
            # Find video file
            for ext in self.video_extensions:
                video_files = list(movie_dir.glob(f'*{ext}'))
                if video_files:
                    # Prefer file with same name as folder
                    folder_name = movie_dir.name
                    for vf in video_files:
                        if vf.stem == folder_name or folder_name in vf.stem:
                            result['video'] = str(vf)
                            break
                    if not result['video']:
                        result['video'] = str(video_files[0])
                    break
        
        # Find poster in movie folder
        result['poster'] = self.find_poster_in_folder(str(movie_dir))
        
        # Check parent folder for poster (for single-file movies in series folders)
        if not result['poster']:
            parent_dir = movie_dir.parent
            if parent_dir != movie_dir:
                result['poster'] = self.find_poster_in_folder(str(parent_dir))
        
        # Find subtitles
        movie_dir_for_subs = Path(result['video']).parent if result['video'] else movie_dir
        for sub_file in movie_dir_for_subs.glob('*.srt'):
            result['subtitles'].append(str(sub_file))
        for sub_file in movie_dir_for_subs.glob('*.sub'):
            result['subtitles'].append(str(sub_file))
        
        logger.info(f"Movie files for {movie_path}: video={result['video']}, poster={result['poster']}")
        return result
    
    def get_series_files(self, series_path: str, season: int = None, episode: int = None) -> Dict:
        """Get all media files for a TV series"""
        result = {
            'series': {
                'poster': None,
                'backdrop': None
            },
            'seasons': {},
            'episodes': []
        }
        
        series_dir = Path(series_path)
        if not series_dir.exists():
            return result
        
        # Series-level poster
        result['series']['poster'] = self.find_poster_in_folder(str(series_dir))
        
        # Find season folders
        season_dirs = []
        for d in series_dir.iterdir():
            if d.is_dir():
                # Check if it's a season folder
                if 'Season' in d.name or 'season' in d.name:
                    season_dirs.append(d)
                else:
                    # Could be a folder with episodes directly (no season subfolders)
                    for ext in self.video_extensions:
                        if list(d.glob(f'*{ext}')):
                            season_dirs.append(d)
                            break
        
        if not season_dirs:
            # Check if series folder itself contains episodes
            for ext in self.video_extensions:
                if list(series_dir.glob(f'*{ext}')):
                    season_dirs.append(series_dir)
                    break
        
        for season_dir in season_dirs:
            season_num = self._extract_season_number(season_dir.name)
            if season_num is None:
                season_num = 1
            
            season_data = {
                'poster': self.find_poster_in_folder(str(season_dir)),
                'episodes': []
            }
            
            for ext in self.video_extensions:
                for video_file in season_dir.glob(f'*{ext}'):
                    episode_num = self._extract_episode_number(video_file.stem)
                    episode_data = {
                        'file': str(video_file),
                        'episode': episode_num if episode_num else len(season_data['episodes']) + 1,
                        'title': video_file.stem.replace('_', ' ').replace('.', ' '),
                        'thumbnail': None
                    }
                    season_data['episodes'].append(episode_data)
            
            season_data['episodes'].sort(key=lambda x: x.get('episode', 0))
            result['seasons'][season_num] = season_data
        
        if season and episode:
            if season in result['seasons']:
                for ep in result['seasons'][season].get('episodes', []):
                    if ep.get('episode') == episode:
                        result['episodes'].append(ep)
        
        return result
    
    def _extract_season_number(self, folder_name: str) -> Optional[int]:
        patterns = [
            r'[Ss]eason\s*(\d{1,2})',
            r'[Ss](\d{1,2})',
            r'Season\.(\d{1,2})',
            r'(\d{1,2})\s*[Ss]eason'
        ]
        for pattern in patterns:
            match = re.search(pattern, folder_name)
            if match:
                return int(match.group(1))
        return None
    
    def _extract_episode_number(self, filename: str) -> Optional[int]:
        patterns = [
            r'[Ee](\d{1,3})',
            r'(\d{1,3})x\d{1,3}',
            r'episode\s*(\d{1,3})',
            r'[Ee]p\s*(\d{1,3})',
            r'(\d{1,3})(?=\.)'
        ]
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                return int(match.group(1))
        return None
    
    def get_playable_url(self, file_path: str) -> str:
        """Get a playable URL for a media file"""
        if not file_path or not os.path.exists(file_path):
            return None
        return f'/api/media/{Path(file_path).name}?path={file_path}'