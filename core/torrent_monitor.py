# core/torrent_monitor.py
import os
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
import shutil

logger = logging.getLogger(__name__)


class TorrentMonitor:
    """Monitor download client for completed torrents and move files to library"""
    
    def __init__(self, config_manager, media_mover):
        self.config = config_manager
        self.media_mover = media_mover
        self.running = False
        self.monitor_thread = None
        self.scan_interval = 30  # seconds
        self.processed_files = set()
        
    def start_monitoring(self):
        """Start the torrent monitoring thread"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Torrent monitoring started")
    
    def stop_monitoring(self):
        """Stop the torrent monitoring thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Torrent monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self._check_downloads_folder()
                time.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Error in torrent monitor loop: {e}")
                time.sleep(self.scan_interval)
    
    def _check_downloads_folder(self):
        """Check downloads folder for completed files"""
        downloads_path = self.config.get('paths.downloads', 'downloads')
        
        if not os.path.exists(downloads_path):
            return
        
        video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
        
        for root, dirs, files in os.walk(downloads_path):
            for file in files:
                file_path = os.path.join(root, file)
                
                # Skip if already processed
                if file_path in self.processed_files:
                    continue
                
                # Check if it's a video file
                if Path(file).suffix.lower() in video_extensions:
                    # Check if file is stable (not being written to)
                    if self._is_file_stable(file_path):
                        logger.info(f"Found completed download: {file_path}")
                        self._process_completed_download(file_path)
                        self.processed_files.add(file_path)
    
    def _is_file_stable(self, file_path, wait_seconds=5):
        """Check if file is no longer being written to"""
        try:
            initial_size = os.path.getsize(file_path)
            time.sleep(wait_seconds)
            final_size = os.path.getsize(file_path)
            return initial_size == final_size and initial_size > 0
        except Exception:
            return False
    
    def _process_completed_download(self, file_path):
        """Process a completed download and move to library"""
        try:
            # Try to identify the media
            media_info = self._identify_media(file_path)
            
            if not media_info:
                logger.warning(f"Could not identify media type for: {file_path}")
                return
            
            # Determine destination
            if media_info['type'] == 'movie':
                dest_path = self._get_movie_destination(media_info)
            else:
                dest_path = self._get_tv_destination(media_info)
            
            if not dest_path:
                logger.warning(f"Could not determine destination for: {file_path}")
                return
            
            # Create destination directory
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Move the file
            shutil.move(file_path, dest_path)
            logger.info(f"Moved completed download to: {dest_path}")
            
            # Move associated files (subtitles, nfo, etc.)
            self._move_associated_files(file_path, dest_path)
            
            # Update database if needed
            self._update_database(media_info, dest_path)
            
        except Exception as e:
            logger.error(f"Error processing completed download {file_path}: {e}")
    
    def _identify_media(self, file_path):
        """Identify if file is movie or TV episode"""
        import re
        filename = Path(file_path).stem
        
        # Check for TV patterns
        tv_patterns = [
            r'[Ss]\d{1,2}[Ee]\d{1,3}',
            r'\d{1,2}x\d{1,3}',
            r'[Ee]pisode\s*\d{1,3}',
        ]
        
        for pattern in tv_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                show_name = re.split(pattern, filename, flags=re.IGNORECASE)[0]
                show_name = show_name.replace('.', ' ').replace('_', ' ').strip()
                
                s_e_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', filename, re.IGNORECASE)
                if s_e_match:
                    season = int(s_e_match.group(1))
                    episode = int(s_e_match.group(2))
                else:
                    x_match = re.search(r'(\d{1,2})x(\d{1,3})', filename, re.IGNORECASE)
                    if x_match:
                        season = int(x_match.group(1))
                        episode = int(x_match.group(2))
                    else:
                        season = 1
                        episode = 1
                
                return {
                    'type': 'tv',
                    'title': show_name,
                    'season': season,
                    'episode': episode,
                    'filename': filename
                }
        
        # Assume movie
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
    
    def _get_movie_destination(self, media_info):
        """Get destination path for movie"""
        title = self._sanitize_filename(media_info['title'])
        year = media_info.get('year', '')
        
        if year:
            folder_name = f"{title} ({year})"
        else:
            folder_name = title
        
        extension = '.mkv'
        movies_path = self.config.get('paths.movies', 'media/movies')
        
        dest_folder = os.path.join(movies_path, folder_name)
        dest_path = os.path.join(dest_folder, f"{folder_name}{extension}")
        
        return dest_path
    
    def _get_tv_destination(self, media_info):
        """Get destination path for TV episode"""
        title = self._sanitize_filename(media_info['title'])
        season = media_info['season']
        episode = media_info['episode']
        
        tv_path = self.config.get('paths.tv_shows', 'media/tv')
        series_folder = os.path.join(tv_path, title)
        season_folder = os.path.join(series_folder, f"Season {season:02d}")
        
        extension = '.mkv'
        filename = f"{title} - S{season:02d}E{episode:02d}{extension}"
        dest_path = os.path.join(season_folder, filename)
        
        return dest_path
    
    def _move_associated_files(self, source_path, dest_path):
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
    
    def _update_database(self, media_info, file_path):
        """Update database with the new file location"""
        from core.database import db, MediaItem
        from flask import current_app
        
        with current_app.app_context():
            if media_info['type'] == 'movie':
                media = MediaItem.query.filter_by(
                    media_type='movie',
                    title=media_info['title']
                ).first()
            else:
                media = MediaItem.query.filter_by(
                    media_type='series',
                    title=media_info['title']
                ).first()
            
            if media:
                media.file_path = file_path
                db.session.commit()
                logger.info(f"Updated database for: {media_info['title']}")
    
    def _sanitize_filename(self, filename):
        """Remove invalid characters from filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        return filename.strip()