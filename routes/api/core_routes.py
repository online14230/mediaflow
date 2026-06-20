# routes/api/core_routes.py
import os
import urllib.parse
import mimetypes
import logging
import re
from flask import request, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime

from core import db, MediaItem, UserRequest
from core.config_manager import config_manager
from . import api_bp

logger = logging.getLogger(__name__)


def get_services():
    from app import services, watch_manager, recommendation_engine, user_manager, torrent_indexers, media_searcher, metadata_fixer, youtube_fetcher
    return {
        'metadata': services['metadata'],
        'watch_manager': watch_manager,
        'recommendation_engine': recommendation_engine,
        'user_manager': user_manager,
        'torrent_indexers': torrent_indexers,
        'media_searcher': media_searcher,
        'metadata_fixer': metadata_fixer,
        'youtube_fetcher': youtube_fetcher
    }


@api_bp.route('/api/search')
@login_required
def api_search():
    query = request.args.get('q', '')
    media_type = request.args.get('type', 'movie')
    services = get_services()
    if media_type == 'movie':
        results = services['metadata'].search_movies(query)
    else:
        results = services['metadata'].search_tv_series(query)
    return jsonify({'results': results})


@api_bp.route('/api/add', methods=['POST'])
@login_required
def api_add():
    from core.folder_manager import FolderManager
    import requests
    
    folder_manager = FolderManager(config_manager)
    
    data = request.json
    media_type = data.get('type')
    external_id = data.get('external_id')
    services = get_services()
    
    if media_type == 'movie':
        metadata = services['metadata'].get_movie_details(external_id)
        if metadata:
            folder_path = None
            if config_manager.get('auto_create_folders', 'true') == 'true':
                folder_path = folder_manager.create_movie_folder(metadata['title'], metadata.get('year'))
                
                if folder_path and config_manager.get('auto_download_posters', 'true') == 'true':
                    if metadata.get('poster_path'):
                        poster_url = f"https://image.tmdb.org/t/p/w500{metadata['poster_path']}"
                        folder_manager.save_poster(folder_path, poster_url)
            
            item = MediaItem(
                media_type='movie',
                title=metadata['title'],
                year=metadata.get('year'),
                overview=metadata.get('overview', ''),
                poster_path=metadata.get('poster_path'),
                path=folder_path if folder_path else '',
                external_id=str(external_id),
                added_date=datetime.utcnow()
            )
            db.session.add(item)
            db.session.commit()
            return jsonify({'success': True, 'message': f'Added {metadata["title"]}'})
    
    elif media_type == 'series' or media_type == 'tv':
        metadata = services['metadata'].get_series_details(external_id)
        if metadata:
            folder_path = None
            if config_manager.get('auto_create_folders', 'true') == 'true':
                folder_path = folder_manager.create_series_folder(metadata['title'], metadata.get('year'))
                
                if folder_path and config_manager.get('auto_download_posters', 'true') == 'true':
                    if metadata.get('poster_path'):
                        poster_url = f"https://image.tmdb.org/t/p/w500{metadata['poster_path']}"
                        folder_manager.save_poster(folder_path, poster_url)
            
            item = MediaItem(
                media_type='series',
                title=metadata['title'],
                year=metadata.get('year'),
                overview=metadata.get('overview', ''),
                poster_path=metadata.get('poster_path'),
                path=folder_path if folder_path else '',
                external_id=str(external_id),
                added_date=datetime.utcnow()
            )
            db.session.add(item)
            db.session.commit()
            return jsonify({'success': True, 'message': f'Added {metadata["title"]}'})
    
    return jsonify({'success': False, 'message': 'Failed to add media'})


@api_bp.route('/api/stats')
@login_required
def api_stats():
    return jsonify({
        'movies': MediaItem.query.filter_by(media_type='movie').count(),
        'series': MediaItem.query.filter_by(media_type='series').count(),
        'pending_requests': UserRequest.query.filter_by(status='pending').count(),
        'active_downloads': 0
    })


@api_bp.route('/api/watch/progress', methods=['POST'])
@login_required
def update_watch_progress():
    data = request.json
    services = get_services()
    services['watch_manager'].update_progress(
        user_id=current_user.id,
        media_id=data.get('media_id'),
        media_type=data.get('media_type'),
        position_seconds=data.get('position', 0),
        duration_seconds=data.get('duration', 1)
    )
    return jsonify({'success': True})


@api_bp.route('/api/user/stats')
@login_required
def user_stats():
    services = get_services()
    stats = services['user_manager'].get_user_stats(current_user.id)
    return jsonify(stats)


@api_bp.route('/api/recommendations')
@login_required
def get_recommendations():
    services = get_services()
    recommendations = services['recommendation_engine'].get_recommendations(current_user.id, limit=12)
    return jsonify([{
        'id': r.id,
        'title': r.title,
        'year': r.year,
        'type': r.media_type
    } for r in recommendations])


@api_bp.route('/api/config', methods=['GET', 'POST'])
@login_required
def api_config():
    if not current_user.is_admin:
        return jsonify({'success': False}), 403
    if request.method == 'POST':
        key = request.json.get('key')
        value = request.json.get('value')
        if config_manager.set(key, value):
            return jsonify({'success': True})
        return jsonify({'success': False}), 400
    return jsonify(config_manager.get_all())


@api_bp.route('/api/collection/create', methods=['POST'])
@login_required
def api_create_collection():
    from core.collections import CollectionManager
    collection_manager = CollectionManager()
    data = request.json
    collection = collection_manager.create_collection(
        name=data.get('name'),
        user_id=current_user.id,
        description=data.get('description')
    )
    if data.get('is_public') is not None:
        collection.is_public = data.get('is_public')
        db.session.commit()
    return jsonify({'success': True, 'id': collection.id})


@api_bp.route('/api/indexers/list')
@login_required
def list_indexers():
    indexers = config_manager.get('torrent_indexers', [])
    return jsonify({'indexers': indexers})


@api_bp.route('/api/indexers/refresh', methods=['POST'])
@login_required
def refresh_indexers():
    from core.torrent_indexers import TorrentIndexerManager
    torrent_indexers = TorrentIndexerManager(config_manager)
    torrent_indexers.refresh_indexers()
    return jsonify({'success': True, 'message': 'Indexers refreshed'})


@api_bp.route('/api/indexers/update', methods=['POST'])
@login_required
def update_indexers():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin required'}), 403
    data = request.json
    indexers = data.get('indexers', [])
    config_manager.set('torrent_indexers', indexers)
    from core.torrent_indexers import TorrentIndexerManager
    torrent_indexers = TorrentIndexerManager(config_manager)
    torrent_indexers.refresh_indexers()
    return jsonify({'success': True, 'message': 'Indexers updated'})


@api_bp.route('/api/monitor/status')
@login_required
def monitor_status():
    from app import folder_monitor
    return jsonify({
        'running': folder_monitor.running,
        'observers': len(folder_monitor.observers)
    })


@api_bp.route('/api/media/<path:filename>')
@login_required
def serve_media(filename):
    """Serve media files (posters, backdrops, etc.) with proper path handling"""
    from flask import send_file, abort
    
    file_path = request.args.get('path')
    
    if not file_path:
        # Try to find the file by searching the database
        media_item = MediaItem.query.filter(
            (MediaItem.poster_path == filename) | 
            (MediaItem.poster_path.endswith(filename)) |
            (MediaItem.backdrop_path == filename) |
            (MediaItem.backdrop_path.endswith(filename))
        ).first()
        
        if media_item:
            if media_item.poster_path and os.path.exists(media_item.poster_path):
                file_path = media_item.poster_path
            elif media_item.backdrop_path and os.path.exists(media_item.backdrop_path):
                file_path = media_item.backdrop_path
        
        if not file_path:
            return "NO POSTER: No file path provided", 404
    
    # URL decode the path
    try:
        file_path = urllib.parse.unquote(file_path)
    except Exception as e:
        logger.error(f"Failed to decode path: {e}")
        return "NO POSTER: Invalid path encoding", 400
    
    # Fix common path issues
    file_path = file_path.replace('%3A', ':').replace('%5C', '\\').replace('%2F', '/')
    
    # Fix the specific issue: "series/Fromposter.jpg" -> "series/From/poster.jpg"
    # This handles cases where the slash between series folder and poster is missing
    match = re.search(r'(.*/series/)([^/]+?)(poster|backdrop|folder|cover)(\.\w+)$', file_path, re.IGNORECASE)
    if match:
        base_path, series_name, image_type, ext = match.groups()
        corrected_path = f"{base_path}{series_name}/{image_type}{ext}"
        if os.path.exists(corrected_path):
            logger.info(f"Fixed poster path: {file_path} -> {corrected_path}")
            file_path = corrected_path
    
    # Also handle the case where the path is missing a slash between series and folder
    if 'series/Fromposter' in file_path:
        file_path = file_path.replace('series/Fromposter', 'series/From/poster')
        logger.info(f"Fixed path: {file_path}")
    
    # Check if file exists
    if not os.path.exists(file_path):
        # Try to find the file by searching in media folders
        movies_path = config_manager.get('paths.movies', 'media/movies')
        tv_path = config_manager.get('paths.tv_shows', 'media/tv')
        
        basename = os.path.basename(file_path)
        
        # Try to find in movies folder
        if os.path.exists(movies_path):
            for root, dirs, files in os.walk(movies_path):
                if basename in files:
                    file_path = os.path.join(root, basename)
                    break
        
        # Try to find in TV folder if not found
        if not os.path.exists(file_path) and os.path.exists(tv_path):
            for root, dirs, files in os.walk(tv_path):
                if basename in files:
                    file_path = os.path.join(root, basename)
                    break
        
        if not os.path.exists(file_path):
            logger.warning(f"Poster not found: {file_path}")
            return "NO POSTER: Poster file not found on disk", 404
    
    # Check if it's an image file
    if not file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return "NO POSTER: File is not an image", 400
    
    try:
        # Get the correct mimetype
        mimetype = mimetypes.guess_type(file_path)[0] or 'image/jpeg'
        return send_file(file_path, mimetype=mimetype)
    except Exception as e:
        logger.error(f"Error serving file {file_path}: {e}")
        return f"NO POSTER: Error serving file - {str(e)}", 500


@api_bp.route('/api/series/<int:show_id>/missing')
@login_required
def get_missing_episodes(show_id):
    from core.episode_manager import EpisodeManager
    from core.database import TVShow, Season, Episode
    
    show = MediaItem.query.get_or_404(show_id)
    
    # Get all episodes that should exist (based on TV show data)
    missing = []
    
    tv_show = TVShow.query.filter_by(media_id=show_id).first()
    if tv_show:
        seasons = Season.query.filter_by(tv_show_id=tv_show.id).all()
        for season in seasons:
            # Get existing episodes for this season
            existing_episodes = Episode.query.filter_by(season_id=season.id).all()
            existing_numbers = [ep.episode_number for ep in existing_episodes]
            
            # Check for missing episodes (assuming up to 24 episodes per season)
            for ep_num in range(1, 25):
                if ep_num not in existing_numbers:
                    # Check if there's a file in the folder that might match
                    season_folder = None
                    if show.path:
                        possible_season_folder = os.path.join(show.path, f'Season {season.season_number:02d}')
                        if os.path.exists(possible_season_folder):
                            season_folder = possible_season_folder
                    
                    missing.append({
                        'season': season.season_number,
                        'episode': ep_num,
                        'season_folder': season_folder
                    })
    
    return jsonify({'missing': missing})