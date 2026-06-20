# core/renamer.py - Updated with TVDB/TMDB ID support

import re
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

class MediaRenamer:
    def __init__(self, config: Dict):
        self.movie_config = config.get('movies', {})
        self.tv_config = config.get('tv_shows', {})
    
    def generate_movie_filename(self, title: str, year: str = "", quality: str = "", 
                                extension: str = "", tmdb_id: str = "", imdb_id: str = "") -> str:
        format_str = self.movie_config.get('file_format', '{title} ({year}) [{tmdb_id}]{quality}{extension}')
        result = format_str.format(
            title=title,
            year=year,
            tmdb_id=f" [tmdbid-{tmdb_id}]" if tmdb_id else "",
            imdb_id=f" [imdbid-{imdb_id}]" if imdb_id else "",
            quality=f" [{quality}]" if quality else "",
            extension=extension
        )
        return self._clean(result)
    
    def generate_movie_folder(self, title: str, year: str = "", tmdb_id: str = "", imdb_id: str = "") -> str:
        format_str = self.movie_config.get('folder_format', '{title} ({year}) [tmdbid-{tmdb_id}]')
        result = format_str.format(
            title=title,
            year=year,
            tmdb_id=tmdb_id if tmdb_id else "",
            imdb_id=imdb_id if imdb_id else ""
        )
        return self._clean(result)
    
    def generate_episode_filename(self, title: str, season: int, episode: int, 
                                   episode_title: str = "", quality: str = "", 
                                   extension: str = "", tvdb_id: str = "", tmdb_id: str = "") -> str:
        format_str = self.tv_config.get('episode_format', '{title} - S{season:02d}E{episode:02d} - {episode_title} [tvdbid-{tvdb_id}]{quality}{extension}')
        result = format_str.format(
            title=title,
            season=season,
            episode=episode,
            episode_title=episode_title or f"Episode {episode}",
            tvdb_id=f" [tvdbid-{tvdb_id}]" if tvdb_id else "",
            tmdb_id=f" [tmdbid-{tmdb_id}]" if tmdb_id else "",
            quality=f" [{quality}]" if quality else "",
            extension=extension
        )
        return self._clean(result)
    
    def generate_series_folder(self, title: str, year: str = "", tvdb_id: str = "", tmdb_id: str = "") -> str:
        format_str = self.tv_config.get('series_folder_format', '{title} ({year}) [tvdbid-{tvdb_id}]')
        result = format_str.format(
            title=title,
            year=year,
            tvdb_id=tvdb_id if tvdb_id else "",
            tmdb_id=tmdb_id if tmdb_id else ""
        )
        return self._clean(result)
    
    def generate_season_folder(self, season: int) -> str:
        format_str = self.tv_config.get('season_folder_format', 'Season {season:02d}')
        result = format_str.format(season=season)
        return self._clean(result)
    
    def _clean(self, filename: str) -> str:
        for char in '<>:"/\\|?*':
            filename = filename.replace(char, '_')
        return re.sub(r'\s+', ' ', filename).strip()
    
    def preview_rename(self, file_path: str, media_type: str, **kwargs) -> Dict:
        if media_type == 'movie':
            new_name = self.generate_movie_filename(**kwargs)
        elif media_type == 'episode':
            new_name = self.generate_episode_filename(**kwargs)
        else:
            return {'success': False, 'error': 'Unknown type'}
        return {'success': True, 'old_name': Path(file_path).name, 'new_name': new_name, 'would_rename': True}