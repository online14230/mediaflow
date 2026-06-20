# core/db_health.py
import os
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from flask import current_app
from core.database import db, MediaItem, User, UserRequest, DownloadTask, TVShow, Season, Episode
from core.watch_history import WatchHistory
from core.config_manager import config_manager
import logging

logger = logging.getLogger(__name__)

class DatabaseHealthChecker:
    """Performs health checks and repairs on the MediaFlow database."""

    def __init__(self):
        self.db_path = config_manager.get('database.path', 'data/mediaflow.db')
        if not os.path.isabs(self.db_path):
            self.db_path = str(Path(current_app.root_path) / self.db_path)
        self.conn = None

    def _get_connection(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    # ==================== SCHEMA CHECKS ====================

    def check_missing_columns(self) -> Dict[str, List[str]]:
        """Return dict of table_name -> list of missing required columns."""
        required_columns = {
            'users': ['id', 'username', 'email', 'password_hash', 'is_admin', 'created_at', 'last_login'],
            'media_items': ['id', 'media_type', 'title', 'year', 'overview', 'poster_path', 'backdrop_path',
                            'external_id', 'external_source', 'runtime', 'rating', 'genres', 'director',
                            'path', 'file_path', 'folder_path', 'added_date',
                            'cast', 'writers', 'studios', 'tagline', 'country', 'trailer_url', 'trailers'],
            'tv_shows': ['id', 'media_id', 'tvdb_id', 'tmdb_id', 'imdb_id', 'season_count', 'episode_count',
                         'status', 'network', 'first_air_date', 'last_air_date'],
            'seasons': ['id', 'tv_show_id', 'season_number', 'episode_count', 'poster_path', 'overview', 'air_date'],
            'episodes': ['id', 'season_id', 'episode_number', 'title', 'overview', 'air_date', 'runtime',
                         'still_path', 'file_path', 'downloaded'],
            'user_requests': ['id', 'user_id', 'media_type', 'title', 'status', 'request_date', 'approved_date', 'approved_by'],
            'download_tasks': ['id', 'title', 'status', 'progress', 'added_date'],
            'watch_history': ['id', 'user_id', 'media_id', 'media_type', 'progress', 'position_seconds', 'completed', 'last_played', 'play_count'],
            'media_collections': ['id', 'name', 'description', 'cover_path', 'user_id', 'created_at', 'is_public', 'media_items']
        }

        missing = {}
        conn = self._get_connection()
        for table, cols in required_columns.items():
            # Check if table exists first
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cursor.fetchone():
                missing[table] = cols  # Table missing entirely
                continue
                
            cursor = conn.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}
            missing_cols = [col for col in cols if col not in existing]
            if missing_cols:
                missing[table] = missing_cols
        return missing

    def repair_missing_columns(self) -> Dict[str, List[str]]:
        """Add missing columns to tables. Returns list of added columns per table."""
        missing = self.check_missing_columns()
        added = {}
        conn = self._get_connection()
        cursor = conn.cursor()

        type_map = {
            'id': 'INTEGER PRIMARY KEY',
            'media_id': 'INTEGER',
            'user_id': 'INTEGER',
            'season_id': 'INTEGER',
            'tv_show_id': 'INTEGER',
            'title': 'VARCHAR(500)',
            'username': 'VARCHAR(80)',
            'email': 'VARCHAR(120)',
            'password_hash': 'VARCHAR(200)',
            'is_admin': 'BOOLEAN',
            'created_at': 'TIMESTAMP',
            'last_login': 'TIMESTAMP',
            'media_type': 'VARCHAR(20)',
            'year': 'INTEGER',
            'overview': 'TEXT',
            'poster_path': 'VARCHAR(500)',
            'backdrop_path': 'VARCHAR(500)',
            'external_id': 'VARCHAR(50)',
            'external_source': 'VARCHAR(20)',
            'runtime': 'INTEGER',
            'rating': 'FLOAT',
            'genres': 'TEXT',
            'director': 'VARCHAR(200)',
            'path': 'VARCHAR(1000)',
            'file_path': 'VARCHAR(1000)',
            'folder_path': 'VARCHAR(1000)',
            'added_date': 'TIMESTAMP',
            'cast': 'TEXT',
            'writers': 'TEXT',
            'studios': 'TEXT',
            'tagline': 'VARCHAR(500)',
            'country': 'VARCHAR(100)',
            'trailer_url': 'VARCHAR(500)',
            'trailers': 'TEXT',
            'tvdb_id': 'INTEGER',
            'tmdb_id': 'INTEGER',
            'imdb_id': 'VARCHAR(20)',
            'season_count': 'INTEGER',
            'episode_count': 'INTEGER',
            'status': 'VARCHAR(20)',
            'network': 'VARCHAR(100)',
            'first_air_date': 'VARCHAR(20)',
            'last_air_date': 'VARCHAR(20)',
            'season_number': 'INTEGER',
            'episode_number': 'INTEGER',
            'still_path': 'VARCHAR(500)',
            'downloaded': 'BOOLEAN',
            'request_date': 'TIMESTAMP',
            'approved_date': 'TIMESTAMP',
            'approved_by': 'INTEGER',
            'progress': 'FLOAT',
            'position_seconds': 'INTEGER',
            'completed': 'BOOLEAN',
            'last_played': 'TIMESTAMP',
            'play_count': 'INTEGER',
            'name': 'VARCHAR(200)',
            'description': 'TEXT',
            'cover_path': 'VARCHAR(500)',
            'is_public': 'BOOLEAN',
            'media_items': 'TEXT'
        }

        for table, cols in missing.items():
            added_cols = []
            for col in cols:
                col_type = type_map.get(col, 'TEXT')
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    added_cols.append(col)
                    logger.info(f"Added column {col} to {table}")
                except Exception as e:
                    logger.error(f"Failed to add {col} to {table}: {e}")
            if added_cols:
                added[table] = added_cols
        conn.commit()
        return added

    # ==================== ORPHAN RECORDS ====================

    def check_orphans(self) -> Dict[str, List[int]]:
        """Find records with broken foreign keys."""
        orphans = {}
        
        # Orphan TVShow without MediaItem
        try:
            orphan_tvshows = db.session.query(TVShow.id).filter(~TVShow.media_id.in_(db.session.query(MediaItem.id))).all()
            if orphan_tvshows:
                orphans['tv_shows'] = [r[0] for r in orphan_tvshows]
        except Exception as e:
            logger.warning(f"Could not check TVShow orphans: {e}")
            
        # Orphan Seasons
        try:
            orphan_seasons = db.session.query(Season.id).filter(~Season.tv_show_id.in_(db.session.query(TVShow.id))).all()
            if orphan_seasons:
                orphans['seasons'] = [r[0] for r in orphan_seasons]
        except Exception as e:
            logger.warning(f"Could not check Season orphans: {e}")
            
        # Orphan Episodes
        try:
            orphan_episodes = db.session.query(Episode.id).filter(~Episode.season_id.in_(db.session.query(Season.id))).all()
            if orphan_episodes:
                orphans['episodes'] = [r[0] for r in orphan_episodes]
        except Exception as e:
            logger.warning(f"Could not check Episode orphans: {e}")
            
        # Orphan WatchHistory (media missing)
        try:
            orphan_watch = db.session.query(WatchHistory.id).filter(~WatchHistory.media_id.in_(db.session.query(MediaItem.id))).all()
            if orphan_watch:
                orphans['watch_history'] = [r[0] for r in orphan_watch]
        except Exception as e:
            logger.warning(f"Could not check WatchHistory orphans: {e}")
            
        # Orphan UserRequests (user missing)
        try:
            orphan_requests = db.session.query(UserRequest.id).filter(~UserRequest.user_id.in_(db.session.query(User.id))).all()
            if orphan_requests:
                orphans['user_requests'] = [r[0] for r in orphan_requests]
        except Exception as e:
            logger.warning(f"Could not check UserRequest orphans: {e}")
            
        return orphans

    def repair_orphans(self) -> Dict[str, int]:
        """Delete orphaned records. Returns count deleted per table."""
        deleted = {}
        orphans = self.check_orphans()
        
        for table, ids in orphans.items():
            if not ids:
                continue
            try:
                if table == 'tv_shows':
                    count = TVShow.query.filter(TVShow.id.in_(ids)).delete(synchronize_session=False)
                    deleted['tv_shows'] = count
                elif table == 'seasons':
                    count = Season.query.filter(Season.id.in_(ids)).delete(synchronize_session=False)
                    deleted['seasons'] = count
                elif table == 'episodes':
                    count = Episode.query.filter(Episode.id.in_(ids)).delete(synchronize_session=False)
                    deleted['episodes'] = count
                elif table == 'watch_history':
                    count = WatchHistory.query.filter(WatchHistory.id.in_(ids)).delete(synchronize_session=False)
                    deleted['watch_history'] = count
                elif table == 'user_requests':
                    count = UserRequest.query.filter(UserRequest.id.in_(ids)).delete(synchronize_session=False)
                    deleted['user_requests'] = count
            except Exception as e:
                logger.error(f"Failed to delete orphans from {table}: {e}")
                
        db.session.commit()
        return deleted

    # ==================== DUPLICATE MEDIA ====================

    def check_duplicate_movies(self) -> List[Dict]:
        """Find duplicate movies (same title and year, type=movie)."""
        from sqlalchemy import func
        result = []
        try:
            dup = db.session.query(MediaItem.title, MediaItem.year, func.count(MediaItem.id).label('cnt')) \
                .filter(MediaItem.media_type == 'movie') \
                .group_by(MediaItem.title, MediaItem.year) \
                .having(func.count(MediaItem.id) > 1).all()
            
            for title, year, cnt in dup:
                items = MediaItem.query.filter(MediaItem.media_type == 'movie', MediaItem.title == title, MediaItem.year == year).all()
                result.append({
                    'title': title,
                    'year': year,
                    'count': cnt,
                    'ids': [i.id for i in items]
                })
        except Exception as e:
            logger.error(f"Error checking duplicate movies: {e}")
        return result

    def repair_duplicate_movies(self, keep_oldest: bool = True) -> int:
        """Delete duplicate movies, keeping the one with the earliest added_date (or oldest ID)."""
        duplicates = self.check_duplicate_movies()
        deleted = 0
        for dup in duplicates:
            try:
                items = MediaItem.query.filter(MediaItem.id.in_(dup['ids'])).order_by(MediaItem.added_date.asc()).all()
                keep = items[0]
                to_delete = items[1:]
                for item in to_delete:
                    db.session.delete(item)
                    deleted += 1
            except Exception as e:
                logger.error(f"Failed to delete duplicate {dup['title']}: {e}")
        db.session.commit()
        return deleted

    # ==================== NULL REQUIRED FIELDS ====================

    def check_null_required_fields(self) -> Dict[str, List[int]]:
        """Find media items where title is NULL or media_type is NULL."""
        issues = {}
        try:
            null_title = MediaItem.query.filter(MediaItem.title.is_(None)).all()
            if null_title:
                issues['null_title'] = [m.id for m in null_title]
        except Exception as e:
            logger.warning(f"Could not check null titles: {e}")
            
        try:
            null_type = MediaItem.query.filter(MediaItem.media_type.is_(None)).all()
            if null_type:
                issues['null_media_type'] = [m.id for m in null_type]
        except Exception as e:
            logger.warning(f"Could not check null media types: {e}")
            
        return issues

    def repair_null_fields(self) -> Dict[str, int]:
        """Repair NULL fields by setting defaults."""
        fixed = {}
        try:
            # Set empty string for NULL titles
            count = MediaItem.query.filter(MediaItem.title.is_(None)).update({'title': 'Unknown Title'})
            if count:
                fixed['title'] = count
        except Exception as e:
            logger.error(f"Failed to fix null titles: {e}")
            
        try:
            # Set default media_type 'movie' for NULL
            count = MediaItem.query.filter(MediaItem.media_type.is_(None)).update({'media_type': 'movie'})
            if count:
                fixed['media_type'] = count
        except Exception as e:
            logger.error(f"Failed to fix null media types: {e}")
            
        db.session.commit()
        return fixed

    # ==================== MISSING FILE PATHS ====================

    def check_missing_files(self) -> List[Dict]:
        """Find media items where the stored path does not exist on disk."""
        missing = []
        try:
            items = MediaItem.query.filter(MediaItem.path.isnot(None)).all()
            for item in items:
                if item.path and not os.path.exists(item.path):
                    missing.append({
                        'id': item.id,
                        'title': item.title,
                        'path': item.path
                    })
        except Exception as e:
            logger.error(f"Error checking missing files: {e}")
        return missing

    def repair_missing_files(self, auto_delete: bool = False) -> int:
        """Delete media items with missing files if auto_delete=True. Returns count deleted."""
        if not auto_delete:
            return 0
        missing = self.check_missing_files()
        deleted = 0
        for m in missing:
            try:
                item = MediaItem.query.get(m['id'])
                if item:
                    db.session.delete(item)
                    deleted += 1
            except Exception as e:
                logger.error(f"Failed to delete missing file record {m['id']}: {e}")
        db.session.commit()
        return deleted

    # ==================== FULL HEALTH REPORT ====================

    def full_health_check(self) -> Dict[str, Any]:
        """Run all checks and return a comprehensive report."""
        return {
            'missing_columns': self.check_missing_columns(),
            'orphans': self.check_orphans(),
            'duplicate_movies': self.check_duplicate_movies(),
            'null_required_fields': self.check_null_required_fields(),
            'missing_files': self.check_missing_files(),
            'timestamp': datetime.now().isoformat()
        }

    def full_repair(self, delete_missing_files: bool = False) -> Dict[str, Any]:
        """Run all repairs and return summary."""
        result = {
            'columns_added': self.repair_missing_columns(),
            'orphans_deleted': self.repair_orphans(),
            'duplicates_deleted': self.repair_duplicate_movies(),
            'nulls_fixed': self.repair_null_fields(),
            'missing_files_deleted': 0
        }
        if delete_missing_files:
            result['missing_files_deleted'] = self.repair_missing_files(auto_delete=True)
        return result