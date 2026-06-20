# core/config_manager.py

import json
import os
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ConfigManager:
    _instance = None
    _config = None
    _config_path = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._config_path = Path(__file__).parent.parent / "config" / "variables.json"
            self.load()
    
    def load(self) -> Dict:
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"Config loaded from {self._config_path}")
            else:
                self._config = self._get_default()
                self.save()
                logger.info(f"Default config created at {self._config_path}")
        except Exception as e:
            logger.error(f"Config load error: {e}")
            self._config = self._get_default()
        return self._config
    
    def save(self) -> bool:
        try:
            # Ensure directory exists
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            logger.info(f"Config saved successfully to {self._config_path}")
            return True
        except Exception as e:
            logger.error(f"Config save error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> bool:
        keys = key.split('.')
        config = self._config
        try:
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            config[keys[-1]] = value
            return self.save()
        except Exception as e:
            logger.error(f"Config set error: {e}")
            return False
    
    def get_all(self) -> Dict:
        return self._config.copy()
    
    def get_section(self, section: str) -> Dict:
        return self.get(section, {})
    
    def update_section(self, section: str, values: Dict) -> bool:
        current = self.get_section(section)
        current.update(values)
        return self.set(section, current)
    
    def _get_default(self) -> Dict:
        return {
            "version": "3.0.8",
            "server": {"name": "MediaFlow", "host": "127.0.0.1", "port": 8123, "debug": True, "secret_key": "change-this-in-production"},
            "database": {"path": "data/mediaflow.db", "echo": False},
            "paths": {"movies": "media/movies", "tv_shows": "media/tv", "downloads": "downloads", "logs": "logs", "data": "data"},
            "downloader": {"host": "http://localhost:8080", "username": "admin", "password": "adminadmin", "max_concurrent": 5},
            "transmission": {"host": "http://localhost:9091", "username": "", "password": ""},
            "naming": {
                "movies": {"file_format": "{title} ({year}){quality}{extension}", "folder_format": "{title} ({year})"},
                "tv_shows": {"episode_format": "{title} - S{season:02d}E{episode:02d} - {episode_title}{quality}{extension}", "series_folder_format": "{title} ({year})", "season_folder_format": "Season {season:02d}"}
            },
            "quality": {"default_profile": "1080p", "profiles": {"4k": {"resolution": 2160, "keywords": ["4K", "2160p"]}, "1080p": {"resolution": 1080, "keywords": ["1080p", "FullHD"]}, "720p": {"resolution": 720, "keywords": ["720p", "HD"]}}},
            "metadata": {"providers": {"tmdb": {"enabled": True, "api_key": "", "language": "en-US"}}},
            "ui": {"theme": "dark", "items_per_page": 20, "view_mode": "poster"},
            "renaming": {"auto_rename": False, "preview_before_rename": True, "add_release_group": True},
            "logging": {"level": "INFO"},
            "auto_create_folders": "true",
            "auto_download_posters": "true",
            "torrent_indexers": [
                {
                    "name": "1337x",
                    "enabled": True,
                    "type": "torrent",
                    "base_url": "https://1337x.to",
                    "search_path": "/search/{query}/1/",
                    "api_type": "scrape"
                },
                {
                    "name": "The Pirate Bay",
                    "enabled": True,
                    "type": "torrent",
                    "base_url": "https://thepiratebay.org",
                    "search_path": "/search/{query}/0/99/0",
                    "api_type": "scrape"
                },
                {
                    "name": "YTS",
                    "enabled": True,
                    "type": "torrent",
                    "base_url": "https://yts.mx",
                    "search_path": "/api/v2/list_movies.json?query_term={query}",
                    "api_type": "json"
                },
                {
                    "name": "EZTV",
                    "enabled": True,
                    "type": "torrent",
                    "base_url": "https://eztv.re",
                    "search_path": "/api/get-torrents?imdb_id={query}",
                    "api_type": "json"
                }
            ]
        }

config_manager = ConfigManager()