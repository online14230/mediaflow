# core/episode_manager.py

import os
import re
from pathlib import Path
from datetime import datetime
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class EpisodeManager:
    """Manages TV series episodes, including detection of missing episodes"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
    
    def scan_series_folder(self, series_path: str, max_episodes_per_season: int = 24) -> Dict:
        """Scan a series folder and return episode information including placeholders for missing"""
        result = {
            'series_path': series_path,
            'series_name': Path(series_path).name,
            'seasons': {},
            'total_episodes': 0
        }
        
        if not os.path.exists(series_path):
            return result
        
        # First, find all existing episodes
        existing_episodes = {}
        
        # Look for season folders
        for item in os.listdir(series_path):
            item_path = os.path.join(series_path, item)
            
            # Check if it's a season folder
            season_num = self._extract_season_number(item)
            if season_num is not None and os.path.isdir(item_path):
                episodes = self._scan_season_folder(item_path, season_num)
                if season_num not in existing_episodes:
                    existing_episodes[season_num] = []
                existing_episodes[season_num].extend(episodes)
            else:
                # Check for loose episodes in series root
                if os.path.isfile(item_path) and Path(item_path).suffix.lower() in self.video_extensions:
                    episode_info = self._extract_episode_info(item_path, 1)
                    if episode_info:
                        if 1 not in existing_episodes:
                            existing_episodes[1] = []
                        existing_episodes[1].append(episode_info)
        
        # Now generate full episode lists (including placeholders for missing)
        for season_num, episodes in existing_episodes.items():
            # Find max episode number in this season
            max_episode = max([e.get('episode', 0) for e in episodes]) if episodes else 0
            # Use at least 12 episodes per season, or the max found
            season_max = max(max_episode, max_episodes_per_season)
            
            # Create a dict of existing episodes by number
            existing_dict = {e['episode']: e for e in episodes}
            
            # Build complete list with placeholders
            full_episodes = []
            for ep_num in range(1, season_max + 1):
                if ep_num in existing_dict:
                    full_episodes.append(existing_dict[ep_num])
                else:
                    # Add placeholder for missing episode
                    full_episodes.append({
                        'episode': ep_num,
                        'title': f'Episode {ep_num} (Missing)',
                        'path': None,
                        'file_size': 0,
                        'missing': True
                    })
            
            result['seasons'][season_num] = {
                'path': os.path.join(series_path, f'Season {season_num:02d}'),
                'episodes': full_episodes,
                'episode_count': len(full_episodes)
            }
            result['total_episodes'] += len(full_episodes)
        
        return result
    
    def _extract_season_number(self, folder_name: str) -> Optional[int]:
        """Extract season number from folder name"""
        patterns = [
            r'[Ss]eason\s*(\d{1,2})',
            r'[Ss](\d{1,2})$',
            r'Season\.(\d{1,2})',
            r'(\d{1,2})\s*[Ss]eason'
        ]
        for pattern in patterns:
            match = re.search(pattern, folder_name, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
    
    def _scan_season_folder(self, season_path: str, season_num: int) -> List[Dict]:
        """Scan a season folder for episodes"""
        episodes = []
        
        for file in os.listdir(season_path):
            file_path = os.path.join(season_path, file)
            if os.path.isfile(file_path) and Path(file_path).suffix.lower() in self.video_extensions:
                episode_info = self._extract_episode_info(file_path, season_num)
                if episode_info:
                    episodes.append(episode_info)
        
        return episodes
    
    def _extract_episode_info(self, file_path: str, default_season: int) -> Optional[Dict]:
        """Extract episode number and title from filename"""
        filename = Path(file_path).stem
        
        # Try to extract episode number
        episode_num = None
        episode_title = None
        
        # Pattern 1: S01E02
        match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', filename, re.IGNORECASE)
        if match:
            episode_num = int(match.group(2))
            # Extract title (everything before the pattern)
            title_part = re.split(r'[Ss]\d{1,2}[Ee]\d{1,3}', filename)[0]
            episode_title = title_part.replace('.', ' ').replace('_', ' ').strip()
        
        # Pattern 2: 1x02
        if episode_num is None:
            match = re.search(r'(\d{1,2})x(\d{1,3})', filename, re.IGNORECASE)
            if match:
                episode_num = int(match.group(2))
        
        # Pattern 3: Episode 02
        if episode_num is None:
            match = re.search(r'[Ee]pisode\s*(\d{1,3})', filename, re.IGNORECASE)
            if match:
                episode_num = int(match.group(1))
        
        # Pattern 4: E02
        if episode_num is None:
            match = re.search(r'[Ee](\d{1,3})', filename, re.IGNORECASE)
            if match:
                episode_num = int(match.group(1))
        
        # Pattern 5: Just a number at the end
        if episode_num is None:
            match = re.search(r'[-_\s](\d{1,3})$', filename)
            if match:
                episode_num = int(match.group(1))
        
        if episode_num:
            return {
                'episode': episode_num,
                'title': episode_title or filename,
                'path': file_path,
                'file_size': os.path.getsize(file_path)
            }
        
        return None
    
    def find_missing_episodes(self, series_path: str, total_seasons: int = None, 
                              episodes_per_season: Dict = None) -> List[Dict]:
        """Find missing episodes in a series"""
        scanned = self.scan_series_folder(series_path)
        missing = []
        
        for season_num, season_data in scanned.get('seasons', {}).items():
            for episode in season_data.get('episodes', []):
                if episode.get('missing', False) or (episode.get('path') is None):
                    missing.append({
                        'season': season_num,
                        'episode': episode.get('episode', 0),
                        'series_path': series_path,
                        'series_name': scanned['series_name']
                    })
        
        return missing