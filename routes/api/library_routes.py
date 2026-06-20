# routes/api/library_routes.py
import os
import json
import logging
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from collections import defaultdict

from core import db, MediaItem
from core.config_manager import config_manager
from core.library_scanner import LibraryScanner, DuplicateDetector
from core.nfo_parser import NFOParser
from core.metadata_provider import MetadataProvider
from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/api/scan/now', methods=['POST'])
@login_required
def scan_now():
    from app import folder_monitor
    try:
        folder_monitor.trigger_scan()
        return jsonify({'success': True, 'message': 'Manual scan triggered. Checking for new and deleted files.'})
    except Exception as e:
        logger.error(f"Manual scan error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@api_bp.route('/api/library/scan', methods=['POST'])
@login_required
def library_scan():
    """Scan library for new media with TMDB validation"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin required'}), 403
    
    data = request.json
    media_type = data.get('media_type', 'movies')
    purge = data.get('purge', False)
    
    scanner = LibraryScanner(config_manager)
    nfo_parser = NFOParser()
    
    # Initialize TMDB provider
    tmdb_config = config_manager.get('metadata.providers.tmdb', {})
    tmdb_provider = MetadataProvider(tmdb_config)
    
    movies_path = config_manager.get('paths.movies', 'media/movies')
    tv_path = config_manager.get('paths.tv_shows', 'media/tv')
    
    added_count = 0
    found_count = 0
    deleted_count = 0
    skipped_count = 0
    
    try:
        if media_type in ['movies', 'both']:
            if purge:
                deleted = MediaItem.query.filter_by(media_type='movie').delete()
                deleted_count += deleted
                logger.info(f"Purged {deleted} movies from database")
            
            if os.path.exists(movies_path):
                movies = scanner.scan_movies_folder(movies_path)
                found_count += len(movies)
                
                # Get existing movies for duplicate check
                existing_movies = MediaItem.query.filter_by(media_type='movie').all()
                existing_titles = {}
                for em in existing_movies:
                    normalized = DuplicateDetector.normalize_series_title(em.title)
                    existing_titles[normalized] = em
                
                for movie in movies:
                    normalized_title = DuplicateDetector.normalize_series_title(movie['title'])
                    
                    if normalized_title in existing_titles:
                        skipped_count += 1
                        continue
                    
                    existing = MediaItem.query.filter_by(file_path=movie['path']).first()
                    if existing:
                        skipped_count += 1
                        continue
                    
                    folder_path = os.path.dirname(movie['path'])
                    nfo_path = nfo_parser.find_nfo_file(folder_path, 'movie')
                    
                    if nfo_path:
                        metadata = nfo_parser.parse_movie_nfo(nfo_path)
                        if metadata:
                            item = MediaItem(
                                media_type='movie',
                                title=metadata.get('title', movie['title']),
                                year=metadata.get('year', movie.get('year')),
                                overview=metadata.get('plot', ''),
                                rating=metadata.get('rating'),
                                runtime=metadata.get('runtime'),
                                director=metadata.get('director'),
                                genres=json.dumps(metadata.get('genres', [])),
                                poster_path=metadata.get('poster_path'),
                                backdrop_path=metadata.get('fanart_path'),
                                path=folder_path,
                                file_path=movie['path'],
                                added_date=datetime.utcnow()
                            )
                            db.session.add(item)
                            added_count += 1
                            logger.info(f"Added from NFO: {metadata.get('title')}")
                            continue
                    
                    poster_value = None
                    for ext in ['.jpg', '.jpeg', '.png']:
                        poster_candidate = os.path.join(folder_path, f'poster{ext}')
                        if os.path.exists(poster_candidate):
                            poster_value = poster_candidate
                            break
                        poster_candidate = os.path.join(folder_path, f'folder{ext}')
                        if os.path.exists(poster_candidate):
                            poster_value = poster_candidate
                            break
                    
                    item = MediaItem(
                        media_type='movie',
                        title=movie['title'],
                        year=movie.get('year'),
                        overview=f'Imported from: {movie["filename"]}',
                        poster_path=poster_value,
                        path=folder_path,
                        file_path=movie['path'],
                        added_date=datetime.utcnow()
                    )
                    db.session.add(item)
                    added_count += 1
                    logger.info(f"Added movie: {movie['title']}")
                
                db.session.commit()
        
        if media_type in ['tv', 'both']:
            if purge:
                deleted = MediaItem.query.filter_by(media_type='series').delete()
                deleted_count += deleted
                logger.info(f"Purged {deleted} series from database")
            
            if os.path.exists(tv_path):
                episodes = scanner.scan_tv_folder(tv_path)
                found_count += len(episodes)
                
                # Group by match_key (normalized for matching)
                shows = defaultdict(list)
                for episode in episodes:
                    match_key = episode.get('match_key', DuplicateDetector.normalize_series_title(episode['title']))
                    shows[match_key].append(episode)
                
                # Get existing series for duplicate check
                existing_series = MediaItem.query.filter_by(media_type='series').all()
                existing_titles = {}
                for es in existing_series:
                    normalized = DuplicateDetector.normalize_series_title(es.title)
                    existing_titles[normalized] = es
                
                for match_key, show_episodes in shows.items():
                    # Skip if series already exists
                    if match_key in existing_titles:
                        skipped_count += 1
                        logger.debug(f"Series already exists: {match_key}")
                        continue
                    
                    # Get the display title from first episode
                    display_title = show_episodes[0]['title']
                    
                    # Get series path
                    series_path = None
                    for ep in show_episodes:
                        if ep.get('folder_path'):
                            # Navigate up to find series root
                            path_parts = Path(ep['folder_path']).parts
                            for i, part in enumerate(path_parts):
                                if part.lower() == 'season' and i > 0:
                                    series_path = os.path.join(*path_parts[:i])
                                    break
                            if not series_path:
                                series_path = str(Path(ep['folder_path']).parent)
                            break
                    
                    poster_value = None
                    if series_path:
                        for ext in ['.jpg', '.jpeg', '.png']:
                            for candidate in [os.path.join(series_path, f'poster{ext}'),
                                              os.path.join(series_path, f'folder{ext}'),
                                              os.path.join(series_path, f'show{ext}')]:
                                if os.path.exists(candidate):
                                    poster_value = candidate
                                    break
                            if poster_value:
                                break
                    
                    # Get TMDB ID from first episode if available
                    tmdb_id = show_episodes[0].get('tmdb_id')
                    
                    item = MediaItem(
                        media_type='series',
                        title=display_title,
                        overview=f'Imported from library - {len(show_episodes)} episodes found',
                        poster_path=poster_value,
                        path=series_path,
                        external_id=tmdb_id,
                        external_source='tmdb' if tmdb_id else None,
                        added_date=datetime.utcnow()
                    )
                    db.session.add(item)
                    added_count += 1
                    logger.info(f"Added series: {display_title} ({len(show_episodes)} episodes)")
                
                db.session.commit()
        
        return jsonify({
            'success': True,
            'found': found_count,
            'added': added_count,
            'deleted': deleted_count,
            'skipped': skipped_count,
            'message': f'Found {found_count} items, added {added_count}, deleted {deleted_count}, skipped {skipped_count}'
        })
        
    except Exception as e:
        logger.error(f"Library scan error: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})