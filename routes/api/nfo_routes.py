# routes/api/nfo_routes.py
import os
import json
import urllib.parse
import logging
from flask import request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from core import db, MediaItem
from core.config_manager import config_manager
from core.nfo_parser import NFOParser
from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/api/nfo/import', methods=['POST'])
@login_required
def import_nfo_metadata():
    """Import metadata from NFO files in library folders"""
    data = request.json
    media_type = data.get('type', 'all')
    nfo_parser = NFOParser()
    
    movies_path = config_manager.get('paths.movies', 'media/movies')
    tv_path = config_manager.get('paths.tv_shows', 'media/tv')
    
    imported_count = 0
    updated_count = 0
    error_count = 0
    nfo_files_found = 0
    
    logger.info(f"Starting NFO import - Movies path: {movies_path}, TV path: {tv_path}")
    
    if media_type in ['all', 'movie']:
        if os.path.exists(movies_path):
            logger.info(f"Scanning movies folder: {movies_path}")
            for folder in os.listdir(movies_path):
                folder_path = os.path.join(movies_path, folder)
                if os.path.isdir(folder_path):
                    nfo_path = nfo_parser.find_nfo_file(folder_path, 'movie')
                    if nfo_path:
                        nfo_files_found += 1
                        logger.info(f"Found NFO file: {nfo_path}")
                        try:
                            metadata = nfo_parser.parse_movie_nfo(nfo_path)
                            if metadata:
                                logger.info(f"Parsed metadata for: {metadata.get('title')}")
                                
                                movie = MediaItem.query.filter_by(
                                    media_type='movie',
                                    title=metadata.get('title')
                                ).first()
                                
                                if movie:
                                    if metadata.get('year'):
                                        movie.year = metadata['year']
                                    if metadata.get('plot'):
                                        movie.overview = metadata['plot']
                                    if metadata.get('rating'):
                                        movie.rating = metadata['rating']
                                    if metadata.get('runtime'):
                                        movie.runtime = metadata['runtime']
                                    if metadata.get('director'):
                                        movie.director = metadata['director']
                                    if metadata.get('genres'):
                                        movie.genres = json.dumps(metadata['genres'])
                                    if metadata.get('poster_path'):
                                        movie.poster_path = metadata['poster_path']
                                    if metadata.get('fanart_path'):
                                        movie.backdrop_path = metadata['fanart_path']
                                    if metadata.get('tagline'):
                                        movie.tagline = metadata['tagline']
                                    if metadata.get('country'):
                                        movie.country = metadata['country']
                                    if metadata.get('writers'):
                                        movie.writers = json.dumps(metadata['writers'])
                                    if metadata.get('studios'):
                                        movie.studios = json.dumps(metadata['studios'])
                                    if metadata.get('actors'):
                                        movie.cast = json.dumps(metadata['actors'])
                                    if metadata.get('trailers'):
                                        movie.trailers = json.dumps(metadata['trailers'])
                                        movie.trailer_url = metadata['trailers'][0] if metadata['trailers'] else None
                                    updated_count += 1
                                    logger.info(f"Updated movie: {metadata.get('title')}")
                                else:
                                    movie = MediaItem(
                                        media_type='movie',
                                        title=metadata.get('title', folder),
                                        year=metadata.get('year'),
                                        overview=metadata.get('plot', ''),
                                        rating=metadata.get('rating'),
                                        runtime=metadata.get('runtime'),
                                        director=metadata.get('director'),
                                        genres=json.dumps(metadata.get('genres', [])),
                                        poster_path=metadata.get('poster_path'),
                                        backdrop_path=metadata.get('fanart_path'),
                                        path=folder_path,
                                        added_date=datetime.utcnow(),
                                        tagline=metadata.get('tagline'),
                                        country=metadata.get('country'),
                                        writers=json.dumps(metadata.get('writers', [])),
                                        studios=json.dumps(metadata.get('studios', [])),
                                        cast=json.dumps(metadata.get('actors', [])),
                                        trailers=json.dumps(metadata.get('trailers', [])),
                                        trailer_url=metadata.get('trailers', [None])[0] if metadata.get('trailers') else None
                                    )
                                    db.session.add(movie)
                                    imported_count += 1
                                    logger.info(f"Created new movie: {metadata.get('title')}")
                                
                                db.session.commit()
                            else:
                                logger.warning(f"No metadata parsed from: {nfo_path}")
                                error_count += 1
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error processing NFO in {folder_path}: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        logger.debug(f"No NFO file found in: {folder_path}")
        else:
            logger.warning(f"Movies path does not exist: {movies_path}")
    
    logger.info(f"NFO import complete - Files found: {nfo_files_found}, Imported: {imported_count}, Updated: {updated_count}, Errors: {error_count}")
    
    return jsonify({
        'success': True,
        'imported': imported_count,
        'updated': updated_count,
        'errors': error_count,
        'nfo_files_found': nfo_files_found,
        'message': f'Found {nfo_files_found} NFO files. Imported {imported_count} new items, updated {updated_count} existing items. Errors: {error_count}'
    })


@api_bp.route('/api/nfo/test/<path:folder_path>', methods=['GET'])
@login_required
def test_nfo_parse(folder_path):
    """Test NFO parsing on a specific folder (for debugging)"""
    nfo_parser = NFOParser()
    
    folder_path = urllib.parse.unquote(folder_path)
    
    if not os.path.exists(folder_path):
        return jsonify({'success': False, 'error': f'Folder not found: {folder_path}'})
    
    nfo_path = nfo_parser.find_nfo_file(folder_path, 'movie')
    if not nfo_path:
        return jsonify({'success': False, 'error': f'No NFO file found in {folder_path}'})
    
    try:
        metadata = nfo_parser.parse_movie_nfo(nfo_path)
        if metadata:
            return jsonify({
                'success': True,
                'nfo_path': nfo_path,
                'metadata': {
                    'title': metadata.get('title'),
                    'year': metadata.get('year'),
                    'plot': metadata.get('plot', '')[:200] + '...' if metadata.get('plot') and len(metadata.get('plot', '')) > 200 else metadata.get('plot'),
                    'rating': metadata.get('rating'),
                    'runtime': metadata.get('runtime'),
                    'director': metadata.get('director'),
                    'genres': metadata.get('genres'),
                    'poster_path': metadata.get('poster_path'),
                    'fanart_path': metadata.get('fanart_path')
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to parse NFO file'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@api_bp.route('/api/nfo/export/<int:media_id>', methods=['POST'])
@login_required
def export_nfo_metadata(media_id):
    """Export metadata to NFO file for a media item"""
    nfo_parser = NFOParser()
    
    media_item = MediaItem.query.get_or_404(media_id)
    
    if not media_item.path or not os.path.exists(media_item.path):
        return jsonify({'success': False, 'error': 'Media folder not found'})
    
    metadata = {
        'title': media_item.title,
        'year': media_item.year,
        'overview': media_item.overview,
        'rating': media_item.rating,
        'runtime': media_item.runtime,
        'director': media_item.director,
        'poster_path': media_item.poster_path,
        'backdrop_path': media_item.backdrop_path,
        'tagline': media_item.tagline,
        'country': media_item.country
    }
    
    if media_item.genres:
        try:
            metadata['genres'] = json.loads(media_item.genres) if isinstance(media_item.genres, str) else media_item.genres
        except:
            metadata['genres'] = []
    
    if media_item.writers:
        try:
            metadata['writers'] = json.loads(media_item.writers) if isinstance(media_item.writers, str) else media_item.writers
        except:
            metadata['writers'] = []
    
    if media_item.studios:
        try:
            metadata['studios'] = json.loads(media_item.studios) if isinstance(media_item.studios, str) else media_item.studios
        except:
            metadata['studios'] = []
    
    if media_item.cast:
        try:
            metadata['actors'] = json.loads(media_item.cast) if isinstance(media_item.cast, str) else media_item.cast
        except:
            metadata['actors'] = []
    
    if media_item.trailers:
        try:
            metadata['trailers'] = json.loads(media_item.trailers) if isinstance(media_item.trailers, str) else media_item.trailers
        except:
            metadata['trailers'] = []
    
    if media_item.media_type == 'movie':
        success = nfo_parser.write_movie_nfo(
            os.path.join(media_item.path, 'movie.nfo'),
            metadata
        )
    else:
        success = False
        logger.warning("TV series NFO export not yet implemented")
    
    if success:
        return jsonify({'success': True, 'message': 'NFO file exported successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to export NFO file'})