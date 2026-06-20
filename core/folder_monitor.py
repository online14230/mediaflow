# core/folder_monitor.py - Enhanced with proper duplicate detection and cache

import os
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
import threading
import re
import pickle

logger = logging.getLogger(__name__)


class MediaFolderHandler(FileSystemEventHandler):
    """Handle file system events for media folders"""

    def __init__(self, app, media_type, callback=None, db_callback=None):
        self.app = app
        self.media_type = media_type
        self.callback = callback
        self.db_callback = db_callback
        self.processing_files = set()
        self.last_processed = {}
        self.scan_delay = 2
        self.processed_cache = set()

    def set_processed_cache(self, cache):
        self.processed_cache = cache

    def on_created(self, event):
        if not event.is_directory:
            self._process_file(event.src_path, 'created')
        else:
            self._process_directory(event.src_path, 'created')

    def on_deleted(self, event):
        if not event.is_directory:
            self._process_deleted(event.src_path, 'deleted')
        else:
            self._process_deleted_directory(event.src_path, 'deleted')

    def on_modified(self, event):
        if not event.is_directory:
            self._process_file(event.src_path, 'modified')

    def on_moved(self, event):
        if not event.is_directory:
            self._process_deleted(event.src_path, 'moved')
            time.sleep(0.5)
            self._process_file(event.dest_path, 'moved')

    def _check_file_exists_in_db(self, file_path):
        """Check if file already exists in database"""
        from flask import current_app
        from core.database import MediaItem
        
        # Check cache first
        if file_path in self.processed_cache:
            return True, None
        
        with current_app.app_context():
            try:
                # Check by exact file path
                existing = MediaItem.query.filter_by(file_path=file_path).first()
                if existing:
                    self.processed_cache.add(file_path)
                    return True, existing
                
                # For movies, check by filename
                folder_path = os.path.dirname(file_path)
                folder_name = os.path.basename(folder_path)
                folder_name_clean = re.sub(r'\s*\(\d{4}\)\s*', '', folder_name).strip()
                
                # Check if movie exists by title
                existing_movie = MediaItem.query.filter_by(
                    media_type='movie',
                    title=folder_name_clean
                ).first()
                if existing_movie:
                    self.processed_cache.add(file_path)
                    return True, existing_movie
                
            except Exception as e:
                logger.error(f"Error checking file existence: {e}")
        
        return False, None

    def _process_file(self, file_path, event_type):
        if file_path in self.processing_files:
            return

        if file_path in self.last_processed:
            time_since = time.time() - self.last_processed[file_path]
            if time_since < 5:
                return

        self.processing_files.add(file_path)
        self.last_processed[file_path] = time.time()

        try:
            time.sleep(self.scan_delay)

            video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
            if Path(file_path).suffix.lower() in video_extensions:
                # Check if file already exists in database
                exists, existing = self._check_file_exists_in_db(file_path)
                if exists:
                    logger.debug(f"File/series already in database, skipping: {os.path.basename(file_path)}")
                    self.processing_files.discard(file_path)
                    return
                
                logger.info(f"New media detected via event: {os.path.basename(file_path)} ({event_type})")

                if self.callback:
                    self.callback(file_path, self.media_type)
                
                if self.db_callback:
                    self.db_callback(file_path, 'add')

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
        finally:
            self.processing_files.discard(file_path)

    def _process_directory(self, dir_path, event_type):
        try:
            time.sleep(1)
            logger.info(f"New directory detected: {dir_path} ({event_type})")
            if self.db_callback:
                self.db_callback(dir_path, 'scan_folder')
        except Exception as e:
            logger.error(f"Error processing directory {dir_path}: {e}")

    def _process_deleted(self, file_path, event_type):
        try:
            video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
            if Path(file_path).suffix.lower() in video_extensions:
                logger.info(f"Media file deleted: {file_path}")
                self.processed_cache.discard(file_path)
                if self.db_callback:
                    self.db_callback(file_path, 'remove')
        except Exception as e:
            logger.error(f"Error processing deletion {file_path}: {e}")

    def _process_deleted_directory(self, dir_path, event_type):
        try:
            logger.info(f"Directory deleted: {dir_path}")
            if self.db_callback:
                self.db_callback(dir_path, 'remove_folder')
        except Exception as e:
            logger.error(f"Error processing directory deletion {dir_path}: {e}")


class FolderMonitor:
    """Monitor media folders for changes with periodic scanning and database sync"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.observers = []
        self.running = False
        self.callbacks = []
        self.scan_timer = None
        self.scan_interval_minutes = 30
        self.db_sync_callback = None
        self.last_scan_time = {}
        self.scan_in_progress = False
        self.processed_series = set()
        self.processed_files_cache = set()
        self.app = None
        self._load_cache()

    def set_app(self, app):
        self.app = app

    def _get_cache_path(self):
        """Get path to cache file"""
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "processed_files.cache"

    def _load_cache(self):
        """Load processed files cache from disk"""
        try:
            cache_path = self._get_cache_path()
            if cache_path.exists():
                with open(cache_path, 'rb') as f:
                    self.processed_files_cache = pickle.load(f)
                logger.info(f"Loaded {len(self.processed_files_cache)} files from cache")
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            self.processed_files_cache = set()

    def _save_cache(self):
        """Save processed files cache to disk"""
        try:
            cache_path = self._get_cache_path()
            with open(cache_path, 'wb') as f:
                pickle.dump(self.processed_files_cache, f)
            logger.debug(f"Saved {len(self.processed_files_cache)} files to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def register_callback(self, callback):
        self.callbacks.append(callback)

    def register_db_sync(self, db_callback):
        self.db_sync_callback = db_callback

    def start_monitoring(self):
        try:
            movies_path = self.config.get('paths.movies', 'media/movies')
            if os.path.exists(movies_path):
                self._watch_folder(movies_path, 'movie')
                logger.info(f"Watching movies folder: {movies_path}")
            else:
                logger.warning(f"Movies folder does not exist: {movies_path}")

            tv_path = self.config.get('paths.tv_shows', 'media/tv')
            if os.path.exists(tv_path):
                self._watch_folder(tv_path, 'series')
                logger.info(f"Watching TV series folder: {tv_path}")
            else:
                logger.warning(f"TV series folder does not exist: {tv_path}")

            downloads_path = self.config.get('paths.downloads', 'downloads')
            if os.path.exists(downloads_path):
                self._watch_folder(downloads_path, 'download')
                logger.info(f"Watching downloads folder: {downloads_path}")

            self.running = True
            self._start_periodic_scan()
            logger.info(f"Folder monitoring started with periodic scanning every {self.scan_interval_minutes} minutes")

        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")

    def _watch_folder(self, folder_path, media_type):
        try:
            event_handler = MediaFolderHandler(
                self, media_type, 
                callback=self._on_file_event,
                db_callback=self._on_db_sync
            )
            event_handler.set_processed_cache(self.processed_files_cache)
            observer = Observer()
            observer.schedule(event_handler, folder_path, recursive=True)
            observer.start()
            self.observers.append(observer)
            logger.info(f"Watching: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to watch folder {folder_path}: {e}")

    def _on_file_event(self, file_path, media_type):
        for callback in self.callbacks:
            try:
                callback(file_path, media_type)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def _on_db_sync(self, path, action):
        if self.db_sync_callback:
            try:
                self.db_sync_callback(path, action)
            except Exception as e:
                logger.error(f"DB sync error: {e}")

    def _start_periodic_scan(self):
        # Run first scan after a delay to let the app fully start
        self.scan_timer = threading.Timer(60, self._periodic_scan_wrapper)
        self.scan_timer.daemon = True
        self.scan_timer.start()

    def _periodic_scan_wrapper(self):
        """Wrapper to ensure app context for periodic scan"""
        from flask import current_app
        try:
            with current_app.app_context():
                self._periodic_scan()
        except RuntimeError:
            if self.app:
                with self.app.app_context():
                    self._periodic_scan()
            else:
                logger.error("No application context available for periodic scan")
        finally:
            if self.running:
                self.scan_timer = threading.Timer(self.scan_interval_minutes * 60, self._periodic_scan_wrapper)
                self.scan_timer.daemon = True
                self.scan_timer.start()

    def _periodic_scan(self):
        if not self.running or self.scan_in_progress:
            return

        self.scan_in_progress = True
        try:
            logger.info("Running periodic folder scan...")

            movies_path = self.config.get('paths.movies', 'media/movies')
            if os.path.exists(movies_path):
                self._scan_for_new_files(movies_path, 'movie')

            tv_path = self.config.get('paths.tv_shows', 'media/tv')
            if os.path.exists(tv_path):
                self._scan_for_new_files(tv_path, 'series')

            downloads_path = self.config.get('paths.downloads', 'downloads')
            if os.path.exists(downloads_path):
                self._scan_for_new_files(downloads_path, 'download')

            self._save_cache()
            logger.info("Periodic folder scan completed")
        except Exception as e:
            logger.error(f"Periodic scan error: {e}")
        finally:
            self.scan_in_progress = False

    def _check_series_exists(self, series_name):
        """Check if a series already exists in the database"""
        from core.database import MediaItem
        
        try:
            existing = MediaItem.query.filter_by(
                media_type='series',
                title=series_name
            ).first()
            return existing is not None
        except Exception as e:
            logger.error(f"Error checking series exists: {e}")
            return True

    def _scan_for_new_files(self, folder_path, media_type):
        """Scan for new files - checks database and cache before adding"""
        from core.database import MediaItem
        
        video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
        new_files = []
        processed_series_this_scan = set()

        try:
            # Get all existing file paths from database once
            existing_file_paths = set()
            all_media = MediaItem.query.all()
            for media in all_media:
                if media.file_path:
                    existing_file_paths.add(media.file_path)
                    self.processed_files_cache.add(media.file_path)
                if media.path and os.path.isfile(media.path):
                    existing_file_paths.add(media.path)
                    self.processed_files_cache.add(media.path)
            
            logger.debug(f"Found {len(existing_file_paths)} existing files in database")
            
            for root, dirs, files in os.walk(folder_path):
                if media_type == 'movie' and ('Season' in root or 'season' in root):
                    continue
                    
                if media_type == 'series':
                    parts = Path(root).parts
                    series_name = None
                    for i, part in enumerate(parts):
                        if part.lower() == 'season' and i > 0:
                            series_name = parts[i-1]
                            break
                    
                    if not series_name:
                        series_name = Path(root).parent.name if 'Season' in root else Path(root).name
                    
                    series_name_clean = re.sub(r'\s*\(\d{4}\)\s*', '', series_name).strip()
                    
                    series_key = f"{folder_path}_{series_name_clean}"
                    if series_key in processed_series_this_scan:
                        continue
                    
                    if self._check_series_exists(series_name_clean):
                        logger.debug(f"Series already in database, skipping: {series_name_clean}")
                        processed_series_this_scan.add(series_key)
                        dirs.clear()
                        continue
                
                for file in files:
                    if Path(file).suffix.lower() in video_extensions and 'sample' not in file.lower():
                        file_path = os.path.join(root, file)
                        
                        # Check cache
                        if file_path in self.processed_files_cache:
                            logger.debug(f"File in cache, skipping: {file}")
                            continue
                        
                        # Check database
                        if file_path in existing_file_paths:
                            logger.debug(f"File already in database, skipping: {file}")
                            self.processed_files_cache.add(file_path)
                            continue
                        
                        # Also check by filename for movies
                        if media_type == 'movie':
                            folder_name = os.path.basename(root)
                            folder_name_clean = re.sub(r'\s*\(\d{4}\)\s*', '', folder_name).strip()
                            existing_movie = MediaItem.query.filter_by(
                                media_type='movie',
                                title=folder_name_clean
                            ).first()
                            if existing_movie:
                                logger.debug(f"Movie already in database by title, skipping: {folder_name_clean}")
                                self.processed_files_cache.add(file_path)
                                continue
                        
                        # This is a genuinely new file
                        new_files.append(file_path)
                        logger.info(f"Found new file to add: {file}")
                        self.processed_files_cache.add(file_path)

            if new_files:
                logger.info(f"Found {len(new_files)} new files in {folder_path}")
                for file_path in new_files:
                    for callback in self.callbacks:
                        try:
                            callback(file_path, media_type)
                        except Exception as e:
                            logger.error(f"Callback error for {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error scanning folder {folder_path}: {e}")

    def scan_for_deleted_files(self):
        from core.database import db, MediaItem
        
        deleted_count = 0
        try:
            media_items = MediaItem.query.all()
            
            for item in media_items:
                file_missing = False
                if item.file_path and not os.path.exists(item.file_path):
                    file_missing = True
                elif item.path and not os.path.exists(item.path):
                    file_missing = True
                
                if file_missing:
                    logger.info(f"File missing from disk, deleting from DB: {item.title}")
                    db.session.delete(item)
                    deleted_count += 1
                    if item.file_path:
                        self.processed_files_cache.discard(item.file_path)
                    if item.path:
                        self.processed_files_cache.discard(item.path)
            
            if deleted_count > 0:
                db.session.commit()
                self._save_cache()
                logger.info(f"Removed {deleted_count} media items with missing files")
        except Exception as e:
            logger.error(f"Error scanning for deleted files: {e}")
        
        return deleted_count

    def scan_existing(self, folder_path=None):
        if not folder_path:
            folders = [
                self.config.get('paths.movies', 'media/movies'),
                self.config.get('paths.tv_shows', 'media/tv')
            ]
        else:
            folders = [folder_path]

        found_files = []
        video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}

        for folder in folders:
            if not os.path.exists(folder):
                continue

            for root, dirs, files in os.walk(folder):
                for file in files:
                    if Path(file).suffix.lower() in video_extensions and 'sample' not in file.lower():
                        found_files.append(os.path.join(root, file))

        return found_files

    def trigger_scan(self):
        logger.info("Manual scan triggered")
        
        self.processed_series.clear()
        
        deleted = self.scan_for_deleted_files()
        if deleted > 0:
            logger.info(f"Removed {deleted} deleted files from database")
        
        self._periodic_scan()
        return True

    def stop_monitoring(self):
        self.running = False
        if self.scan_timer:
            self.scan_timer.cancel()
            self.scan_timer = None

        for observer in self.observers:
            try:
                observer.stop()
                observer.join(timeout=2)
            except Exception as e:
                logger.error(f"Error stopping observer: {e}")
        
        self.observers.clear()
        self._save_cache()
        logger.info("Folder monitoring stopped")