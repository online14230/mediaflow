# core/media_mover.py

import os
import shutil
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class MediaMover:
    """Move downloaded media to appropriate library folders"""

    def __init__(self, config_manager, episode_manager):
        self.config = config_manager
        self.episode_manager = episode_manager
        self.movies_path = config_manager.get('paths.movies', 'media/movies')
        self.tv_path = config_manager.get('paths.tv_shows', 'media/tv')
        self.downloads_path = config_manager.get('paths.downloads', 'downloads')

    def process_completed_download(self, file_path: str, category: str = None) -> Dict:
        """Process a completed download and move to appropriate library"""
        result = {
            'success': False,
            'original_path': file_path,
            'new_path': None,
            'media_type': None,
            'error': None
        }

        if not os.path.exists(file_path):
            result['error'] = "File does not exist"
            return result

        # Determine media type
        media_info = self._identify_media(file_path)

        if not media_info:
            result['error'] = "Could not identify media type"
            return result

        result['media_type'] = media_info['type']

        # Determine destination path
        if media_info['type'] == 'movie':
            dest_path = self._get_movie_destination(media_info)
        elif media_info['type'] == 'tv':
            dest_path = self._get_tv_destination(media_info)
        else:
            result['error'] = "Unknown media type"
            return result

        if not dest_path:
            result['error'] = "Could not determine destination"
            return result

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Handle filename conflicts
        dest_path = self._resolve_conflict(dest_path)

        try:
            # Move file
            shutil.move(file_path, dest_path)
            result['success'] = True
            result['new_path'] = dest_path
            logger.info(f"Moved: {file_path} -> {dest_path}")

            # Also move associated files (subtitles, nfo, etc.)
            self._move_associated_files(file_path, dest_path)

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Failed to move file: {e}")

        return result

    def _identify_media(self, file_path: str) -> Optional[Dict]:
        """Identify if file is movie or TV episode"""
        filename = Path(file_path).stem
        folder_name = Path(file_path).parent.name

        # Check for TV patterns
        tv_patterns = [
            r'[Ss]\d{1,2}[Ee]\d{1,3}',  # S01E01
            r'\d{1,2}x\d{1,3}',  # 1x01
            r'[Ee]pisode\s*\d{1,3}',  # Episode 01
        ]

        for pattern in tv_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                # Extract show name (everything before the pattern)
                show_name = re.split(pattern, filename, flags=re.IGNORECASE)[0]
                show_name = show_name.replace('.', ' ').replace('_', ' ').strip()

                # Extract season and episode
                season = 1
                episode = 1

                s_e_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', filename, re.IGNORECASE)
                if s_e_match:
                    season = int(s_e_match.group(1))
                    episode = int(s_e_match.group(2))
                else:
                    x_match = re.search(r'(\d{1,2})x(\d{1,3})', filename, re.IGNORECASE)
                    if x_match:
                        season = int(x_match.group(1))
                        episode = int(x_match.group(2))

                return {
                    'type': 'tv',
                    'title': show_name,
                    'season': season,
                    'episode': episode,
                    'filename': filename
                }

        # Assume movie
        # Try to extract movie name and year
        movie_match = re.search(r'^(.+?)[\.\s_-](\d{4})', filename, re.IGNORECASE)
        if movie_match:
            title = movie_match.group(1).replace('.', ' ').replace('_', ' ').strip()
            year = movie_match.group(2)
        else:
            title = filename.replace('.', ' ').replace('_', ' ').strip()
            year = None

        return {
            'type': 'movie',
            'title': title,
            'year': year,
            'filename': filename
        }

    def _get_movie_destination(self, media_info: Dict) -> Optional[str]:
        """Get destination path for movie"""
        title = self._sanitize_filename(media_info['title'])
        year = media_info.get('year', '')

        if year:
            folder_name = f"{title} ({year})"
        else:
            folder_name = title

        extension = '.mkv'  # Default, will be updated from actual file

        dest_folder = os.path.join(self.movies_path, folder_name)
        dest_path = os.path.join(dest_folder, f"{folder_name}{extension}")

        return dest_path

    def _get_tv_destination(self, media_info: Dict) -> Optional[str]:
        """Get destination path for TV episode"""
        title = self._sanitize_filename(media_info['title'])
        season = media_info['season']
        episode = media_info['episode']

        series_folder = os.path.join(self.tv_path, title)
        season_folder = os.path.join(series_folder, f"Season {season:02d}")
        extension = '.mkv'  # Default

        filename = f"{title} - S{season:02d}E{episode:02d}{extension}"
        dest_path = os.path.join(season_folder, filename)

        return dest_path

    def _move_associated_files(self, source_path: str, dest_path: str):
        """Move associated files (subtitles, nfo, etc.)"""
        source_dir = os.path.dirname(source_path)
        source_name = Path(source_path).stem

        for file in os.listdir(source_dir):
            if file.startswith(source_name) and file != Path(source_path).name:
                ext = Path(file).suffix.lower()
                if ext in ['.srt', '.sub', '.idx', '.nfo', '.jpg', '.png']:
                    source_file = os.path.join(source_dir, file)
                    dest_file = os.path.join(os.path.dirname(dest_path), file)

                    try:
                        shutil.move(source_file, dest_file)
                        logger.info(f"Moved associated file: {file}")
                    except Exception as e:
                        logger.warning(f"Failed to move {file}: {e}")

    def _resolve_conflict(self, file_path: str) -> str:
        """Handle filename conflicts"""
        if not os.path.exists(file_path):
            return file_path

        base = os.path.splitext(file_path)[0]
        ext = os.path.splitext(file_path)[1]
        counter = 1

        while os.path.exists(file_path):
            file_path = f"{base}_{counter}{ext}"
            counter += 1

        return file_path

    def _sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        return filename.strip()