# core/media_searcher.py

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class MediaSearcher:
    """Search for missing media across indexers and add to download client"""

    def __init__(self, config_manager, download_client=None):
        self.config = config_manager
        self.download_client = download_client
        self.indexers = []

    def set_download_client(self, download_client):
        """Set the download client for adding torrents"""
        self.download_client = download_client

    def search_movie(self, title: str, year: int = None, quality: str = '1080p') -> List[Dict]:
        """Search for a movie torrent"""
        results = []

        # Build search query
        query = title
        if year:
            query += f" {year}"
        if quality:
            query += f" {quality}"

        logger.info(f"Searching for movie: {query}")

        # Mock results for demonstration
        mock_results = [
            {
                'title': f'{title}.{quality}.BluRay.x264-GROUP',
                'size': '8.5 GB',
                'size_bytes': 9126805504,
                'seeders': 45,
                'leechers': 12,
                'magnet': f'magnet:?xt=urn:btih:example1&dn={title.replace(" ", "+")}+{quality}',
                'indexer': 'Example Indexer 1',
                'quality': quality,
                'download_url': f'magnet:?xt=urn:btih:example1&dn={title.replace(" ", "+")}'
            },
            {
                'title': f'{title}.{quality}.WEB-DL.x264-GROUP2',
                'size': '6.2 GB',
                'size_bytes': 6657199308,
                'seeders': 32,
                'leechers': 8,
                'magnet': f'magnet:?xt=urn:btih:example2&dn={title.replace(" ", "+")}+WEB-DL',
                'indexer': 'Example Indexer 2',
                'quality': quality,
                'download_url': f'magnet:?xt=urn:btih:example2&dn={title.replace(" ", "+")}'
            }
        ]

        return mock_results

    def search_episode(self, series_title: str, season: int, episode: int,
                       quality: str = '1080p') -> List[Dict]:
        """Search for a TV episode torrent"""
        results = []

        # Build search query
        query = f"{series_title} S{season:02d}E{episode:02d} {quality}"

        logger.info(f"Searching for episode: {query}")

        # Mock results for demonstration
        mock_results = [
            {
                'title': f'{series_title}.S{season:02d}E{episode:02d}.{quality}.WEB-DL.x264-GROUP1',
                'size': '2.5 GB',
                'size_bytes': 2684354560,
                'seeders': 30,
                'leechers': 8,
                'magnet': f'magnet:?xt=urn:btih:example_ep1&dn={series_title.replace(" ", "+")}+S{season:02d}E{episode:02d}',
                'indexer': 'Example Indexer 1',
                'quality': quality,
                'season': season,
                'episode': episode,
                'download_url': f'magnet:?xt=urn:btih:example_ep1&dn={series_title.replace(" ", "+")}+S{season:02d}E{episode:02d}'
            },
            {
                'title': f'{series_title}.S{season:02d}E{episode:02d}.{quality}.BluRay.x264-GROUP2',
                'size': '3.1 GB',
                'size_bytes': 3328599654,
                'seeders': 25,
                'leechers': 5,
                'magnet': f'magnet:?xt=urn:btih:example_ep2&dn={series_title.replace(" ", "+")}+S{season:02d}E{episode:02d}+BluRay',
                'indexer': 'Example Indexer 2',
                'quality': quality,
                'season': season,
                'episode': episode,
                'download_url': f'magnet:?xt=urn:btih:example_ep2&dn={series_title.replace(" ", "+")}+S{season:02d}E{episode:02d}'
            }
        ]

        return mock_results

    def search_series(self, series_title: str, year: int = None) -> List[Dict]:
        """Search for a complete series"""
        results = []

        query = series_title
        if year:
            query += f" {year}"

        logger.info(f"Searching for series: {query}")

        mock_results = [
            {
                'title': f'{series_title}.Complete.Series.BluRay.x264-GROUP',
                'size': '150 GB',
                'size_bytes': 161061273600,
                'seeders': 20,
                'leechers': 5,
                'magnet': f'magnet:?xt=urn:btih:example_series&dn={series_title.replace(" ", "+")}+Complete',
                'indexer': 'Example Indexer',
                'download_url': f'magnet:?xt=urn:btih:example_series&dn={series_title.replace(" ", "+")}+Complete'
            }
        ]

        return results

    def add_to_download_client(self, magnet: str, save_path: str = None,
                               category: str = None) -> bool:
        """Add torrent to download client"""
        if not self.download_client:
            logger.error("Download client not configured")
            return False

        try:
            success = self.download_client.add_torrent(magnet, save_path, category)
            if success:
                logger.info(f"Successfully added torrent to download client")
            else:
                logger.error(f"Failed to add torrent to download client")
            return success
        except Exception as e:
            logger.error(f"Error adding to download client: {e}")
            return False