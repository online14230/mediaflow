# core/torrent_indexers.py
import logging
from typing import List, Dict, Optional
from .real_torrent_indexers import RealTorrentIndexer

logger = logging.getLogger(__name__)


class TorrentIndexerManager:
    """Manage multiple torrent indexers and search across them"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.real_indexer = RealTorrentIndexer()
        self.cache = {}
        self.cache_duration = 3600

    def refresh_indexers(self):
        logger.info("Refreshing torrent indexers")

    def search_movie(self, title: str, year: int = None, quality: str = '1080p') -> List[Dict]:
        """Search for a movie across all indexers"""
        logger.info(f"Searching for movie: {title} ({year}) - {quality}")
        
        results = self.real_indexer.search_movie(title, year, quality)
        
        logger.info(f"Found {len(results)} total results for {title}")
        
        return results

    def search_episode(self, series_title: str, season: int, episode: int,
                       quality: str = '1080p') -> List[Dict]:
        """Search for a TV episode across all indexers"""
        logger.info(f"Searching for episode: {series_title} S{season:02d}E{episode:02d}")
        
        results = self.real_indexer.search_episode(series_title, season, episode, quality)
        
        logger.info(f"Found {len(results)} total results for {series_title} S{season:02d}E{episode:02d}")
        
        return results

    def search_series(self, series_title: str, year: int = None) -> List[Dict]:
        """Search for a complete series"""
        logger.info(f"Searching for series: {series_title} ({year})")
        
        results = self.real_indexer.search_series(series_title, year)
        
        return results