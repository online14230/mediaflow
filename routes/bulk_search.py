# routes/bulk_search.py - Bulk search and download missing media

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from core import db, MediaItem
from core.media_searcher import MediaSearcher
from core.download_client import DownloadClient
from core.config_manager import config_manager
from core.torrent_indexers import TorrentIndexerManager
import logging
import os

logger = logging.getLogger(__name__)

bulk_search_bp = Blueprint('bulk_search', __name__)
media_searcher = MediaSearcher(config_manager)
torrent_indexers = TorrentIndexerManager(config_manager)

@bulk_search_bp.route('/bulk-search')
@login_required
def bulk_search_page():
    """Page for bulk searching missing media"""
    return render_template('bulk_search.html')

@bulk_search_bp.route('/api/bulk/find-missing-movies', methods=['POST'])
@login_required
def find_missing_movies():
    """Find missing movies based on library scan"""
    # Get list of movies in library
    movies = MediaItem.query.filter_by(media_type='movie').all()
    
    missing = []
    for movie in movies:
        # Check if movie file exists
        if movie.path and not os.path.exists(movie.path):
            missing.append({
                'id': movie.id,
                'title': movie.title,
                'year': movie.year,
                'overview': movie.overview
            })
        elif not movie.path:
            missing.append({
                'id': movie.id,
                'title': movie.title,
                'year': movie.year,
                'overview': movie.overview
            })
    
    return jsonify({'missing': missing, 'total': len(missing)})

@bulk_search_bp.route('/api/bulk/search-missing-movies', methods=['POST'])
@login_required
def search_missing_movies():
    """Search for missing movies"""
    data = request.json
    movie_ids = data.get('movie_ids', [])
    quality = data.get('quality', '1080p')
    
    results = []
    for movie_id in movie_ids:
        movie = MediaItem.query.get(movie_id)
        if movie:
            search_results = torrent_indexers.search_movie(movie.title, movie.year, quality)
            if search_results:
                results.append({
                    'movie_id': movie.id,
                    'title': movie.title,
                    'year': movie.year,
                    'results': search_results
                })
    
    return jsonify({'results': results})

@bulk_search_bp.route('/api/bulk/download-selected', methods=['POST'])
@login_required
def download_selected():
    """Download selected torrents to client"""
    data = request.json
    downloads = data.get('downloads', [])
    client_type = data.get('client_type', 'qbittorrent')
    
    success_count = 0
    failed_count = 0
    
    # Initialize download client
    if client_type == 'transmission':
        from core.transmission_client import TransmissionClient
        client_config = {
            'host': config_manager.get('transmission_host', 'http://localhost:9091'),
            'username': config_manager.get('transmission_username', ''),
            'password': config_manager.get('transmission_password', '')
        }
        downloader = TransmissionClient(client_config)
    else:
        downloader = DownloadClient(config_manager.get('downloader', {}))
    
    for download in downloads:
        magnet = download.get('magnet')
        if magnet:
            try:
                success = downloader.add_torrent(magnet)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Download error: {e}")
                failed_count += 1
    
    return jsonify({'success': success_count, 'failed': failed_count})