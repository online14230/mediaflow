# routes/api/missing_routes.py
import os
import logging
from flask import request, jsonify
from flask_login import login_required, current_user

from core import db, MediaItem
from core.config_manager import config_manager
from .core_routes import get_services
from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/api/missing/posters')
@login_required
def get_missing_posters():
    """Get list of media items missing posters"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    
    movies_missing = MediaItem.query.filter(
        (MediaItem.media_type == 'movie') &
        ((MediaItem.poster_path.is_(None)) | (MediaItem.poster_path == '') | (MediaItem.poster_path == 'None'))
    ).all()
    
    series_missing = MediaItem.query.filter(
        (MediaItem.media_type == 'series') &
        ((MediaItem.poster_path.is_(None)) | (MediaItem.poster_path == '') | (MediaItem.poster_path == 'None'))
    ).all()
    
    return jsonify({
        'movies': [{'id': m.id, 'title': m.title, 'year': m.year, 'path': m.path} for m in movies_missing],
        'series': [{'id': s.id, 'title': s.title, 'year': s.year, 'path': s.path} for s in series_missing],
        'total_movies': len(movies_missing),
        'total_series': len(series_missing)
    })


@api_bp.route('/api/missing/backdrops')
@login_required
def get_missing_backdrops():
    """Get list of media items missing backdrops"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    
    movies_missing = MediaItem.query.filter(
        (MediaItem.media_type == 'movie') &
        ((MediaItem.backdrop_path.is_(None)) | (MediaItem.backdrop_path == '') | (MediaItem.backdrop_path == 'None'))
    ).all()
    
    series_missing = MediaItem.query.filter(
        (MediaItem.media_type == 'series') &
        ((MediaItem.backdrop_path.is_(None)) | (MediaItem.backdrop_path == '') | (MediaItem.backdrop_path == 'None'))
    ).all()
    
    return jsonify({
        'movies': [{'id': m.id, 'title': m.title, 'year': m.year, 'path': m.path} for m in movies_missing],
        'series': [{'id': s.id, 'title': s.title, 'year': s.year, 'path': s.path} for s in series_missing],
        'total_movies': len(movies_missing),
        'total_series': len(series_missing)
    })


@api_bp.route('/api/missing/files')
@login_required
def get_missing_files():
    """Get list of media items where the actual video file is missing from disk"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    
    missing_files = []
    all_media = MediaItem.query.all()
    
    for item in all_media:
        file_missing = False
        if item.file_path and not os.path.exists(item.file_path):
            file_missing = True
        elif item.path and not os.path.exists(item.path):
            file_missing = True
        
        if file_missing:
            missing_files.append({
                'id': item.id,
                'title': item.title,
                'year': item.year,
                'media_type': item.media_type,
                'path': item.file_path or item.path
            })
    
    return jsonify({
        'missing': missing_files,
        'total': len(missing_files)
    })


@api_bp.route('/api/missing/fix-poster/<int:media_id>', methods=['POST'])
@login_required
def fix_missing_poster(media_id):
    """Download missing poster for a specific media item"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    
    media_item = MediaItem.query.get_or_404(media_id)
    services = get_services()
    
    if media_item.media_type == 'movie':
        results = services['metadata_fixer'].search_movie(media_item.title, media_item.year)
        if results:
            details = services['metadata_fixer'].get_movie_details(results[0]['id'])
            if details and details.get('poster_path'):
                media_item.poster_path = details['poster_path']
                db.session.commit()
                
                if media_item.path and os.path.exists(media_item.path):
                    poster_path = os.path.join(media_item.path, 'poster.jpg')
                    services['metadata_fixer'].download_poster(details['poster_path'], poster_path)
                    media_item.poster_path = poster_path
                    db.session.commit()
                
                return jsonify({'success': True, 'message': f'Poster added for {media_item.title}'})
    else:
        results = services['metadata_fixer'].search_tv_series(media_item.title, media_item.year)
        if results:
            details = services['metadata_fixer'].get_series_details(results[0]['id'])
            if details and details.get('poster_path'):
                media_item.poster_path = details['poster_path']
                db.session.commit()
                
                if media_item.path and os.path.exists(media_item.path):
                    poster_path = os.path.join(media_item.path, 'poster.jpg')
                    services['metadata_fixer'].download_poster(details['poster_path'], poster_path)
                    media_item.poster_path = poster_path
                    db.session.commit()
                
                return jsonify({'success': True, 'message': f'Poster added for {media_item.title}'})
    
    return jsonify({'success': False, 'error': 'Could not find matching media or poster'})


@api_bp.route('/api/missing/fix-backdrop/<int:media_id>', methods=['POST'])
@login_required
def fix_missing_backdrop(media_id):
    """Download missing backdrop for a specific media item"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    
    media_item = MediaItem.query.get_or_404(media_id)
    services = get_services()
    
    if media_item.media_type == 'movie':
        results = services['metadata_fixer'].search_movie(media_item.title, media_item.year)
        if results:
            details = services['metadata_fixer'].get_movie_details(results[0]['id'])
            if details and details.get('backdrop_path'):
                media_item.backdrop_path = details['backdrop_path']
                db.session.commit()
                
                if media_item.path and os.path.exists(media_item.path):
                    backdrop_path = os.path.join(media_item.path, 'backdrop.jpg')
                    services['metadata_fixer'].download_backdrop(details['backdrop_path'], backdrop_path)
                    media_item.backdrop_path = backdrop_path
                    db.session.commit()
                
                return jsonify({'success': True, 'message': f'Backdrop added for {media_item.title}'})
    else:
        results = services['metadata_fixer'].search_tv_series(media_item.title, media_item.year)
        if results:
            details = services['metadata_fixer'].get_series_details(results[0]['id'])
            if details and details.get('backdrop_path'):
                media_item.backdrop_path = details['backdrop_path']
                db.session.commit()
                
                if media_item.path and os.path.exists(media_item.path):
                    backdrop_path = os.path.join(media_item.path, 'backdrop.jpg')
                    services['metadata_fixer'].download_backdrop(details['backdrop_path'], backdrop_path)
                    media_item.backdrop_path = backdrop_path
                    db.session.commit()
                
                return jsonify({'success': True, 'message': f'Backdrop added for {media_item.title}'})
    
    return jsonify({'success': False, 'error': 'Could not find matching media or backdrop'})


@api_bp.route('/api/missing/fix-all-posters', methods=['POST'])
@login_required
def fix_all_missing_posters():
    """Download missing posters for all media items"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    
    services = get_services()
    fixed = 0
    failed = 0
    
    items = MediaItem.query.filter(
        (MediaItem.poster_path.is_(None)) | (MediaItem.poster_path == '') | (MediaItem.poster_path == 'None')
    ).all()
    
    for item in items:
        try:
            if item.media_type == 'movie':
                results = services['metadata_fixer'].search_movie(item.title, item.year)
                if results:
                    details = services['metadata_fixer'].get_movie_details(results[0]['id'])
                    if details and details.get('poster_path'):
                        item.poster_path = details['poster_path']
                        
                        if item.path and os.path.exists(item.path):
                            poster_path = os.path.join(item.path, 'poster.jpg')
                            services['metadata_fixer'].download_poster(details['poster_path'], poster_path)
                            item.poster_path = poster_path
                        
                        db.session.commit()
                        fixed += 1
                        logger.info(f"Fixed poster for {item.title}")
                    else:
                        failed += 1
                else:
                    failed += 1
            else:
                results = services['metadata_fixer'].search_tv_series(item.title, item.year)
                if results:
                    details = services['metadata_fixer'].get_series_details(results[0]['id'])
                    if details and details.get('poster_path'):
                        item.poster_path = details['poster_path']
                        
                        if item.path and os.path.exists(item.path):
                            poster_path = os.path.join(item.path, 'poster.jpg')
                            services['metadata_fixer'].download_poster(details['poster_path'], poster_path)
                            item.poster_path = poster_path
                        
                        db.session.commit()
                        fixed += 1
                        logger.info(f"Fixed poster for {item.title}")
                    else:
                        failed += 1
                else:
                    failed += 1
        except Exception as e:
            logger.error(f"Failed to fix poster for {item.title}: {e}")
            failed += 1
    
    return jsonify({
        'success': True,
        'fixed': fixed,
        'failed': failed,
        'total': len(items),
        'message': f'Fixed {fixed} posters, failed {failed}'
    })


@api_bp.route('/api/missing/fix-all-backdrops', methods=['POST'])
@login_required
def fix_all_missing_backdrops():
    """Download missing backdrops for all media items"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    
    services = get_services()
    fixed = 0
    failed = 0
    
    items = MediaItem.query.filter(
        (MediaItem.backdrop_path.is_(None)) | (MediaItem.backdrop_path == '') | (MediaItem.backdrop_path == 'None')
    ).all()
    
    for item in items:
        try:
            if item.media_type == 'movie':
                results = services['metadata_fixer'].search_movie(item.title, item.year)
                if results:
                    details = services['metadata_fixer'].get_movie_details(results[0]['id'])
                    if details and details.get('backdrop_path'):
                        item.backdrop_path = details['backdrop_path']
                        
                        if item.path and os.path.exists(item.path):
                            backdrop_path = os.path.join(item.path, 'backdrop.jpg')
                            services['metadata_fixer'].download_backdrop(details['backdrop_path'], backdrop_path)
                            item.backdrop_path = backdrop_path
                        
                        db.session.commit()
                        fixed += 1
                        logger.info(f"Fixed backdrop for {item.title}")
                    else:
                        failed += 1
                else:
                    failed += 1
            else:
                results = services['metadata_fixer'].search_tv_series(item.title, item.year)
                if results:
                    details = services['metadata_fixer'].get_series_details(results[0]['id'])
                    if details and details.get('backdrop_path'):
                        item.backdrop_path = details['backdrop_path']
                        
                        if item.path and os.path.exists(item.path):
                            backdrop_path = os.path.join(item.path, 'backdrop.jpg')
                            services['metadata_fixer'].download_backdrop(details['backdrop_path'], backdrop_path)
                            item.backdrop_path = backdrop_path
                        
                        db.session.commit()
                        fixed += 1
                        logger.info(f"Fixed backdrop for {item.title}")
                    else:
                        failed += 1
                else:
                    failed += 1
        except Exception as e:
            logger.error(f"Failed to fix backdrop for {item.title}: {e}")
            failed += 1
    
    return jsonify({
        'success': True,
        'fixed': fixed,
        'failed': failed,
        'total': len(items),
        'message': f'Fixed {fixed} backdrops, failed {failed}'
    })


@api_bp.route('/api/missing/delete-missing-files', methods=['POST'])
@login_required
def delete_missing_files():
    """Delete database entries for files that no longer exist on disk"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    
    deleted_count = 0
    all_media = MediaItem.query.all()
    
    for item in all_media:
        file_missing = False
        if item.file_path and not os.path.exists(item.file_path):
            file_missing = True
        elif item.path and not os.path.exists(item.path):
            file_missing = True
        
        if file_missing:
            logger.info(f"Deleting missing file entry: {item.title} - {item.file_path or item.path}")
            db.session.delete(item)
            deleted_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'deleted': deleted_count,
        'message': f'Deleted {deleted_count} entries for missing files'
    })