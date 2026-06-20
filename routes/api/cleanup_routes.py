# routes/api/cleanup_routes.py
import logging
from flask import request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from core import db, MediaItem
from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/api/cleanup-duplicates', methods=['POST'])
@login_required
def cleanup_duplicates():
    """Remove duplicate media entries from database"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin required'}), 403
    
    deleted_count = 0
    
    # Find duplicate movies (same title and year)
    duplicates = db.session.query(
        MediaItem.title, 
        MediaItem.year, 
        func.count(MediaItem.id).label('count')
    ).filter(
        MediaItem.media_type == 'movie'
    ).group_by(
        MediaItem.title, MediaItem.year
    ).having(
        func.count(MediaItem.id) > 1
    ).all()
    
    for dup in duplicates:
        items = MediaItem.query.filter_by(
            media_type='movie',
            title=dup[0],
            year=dup[1]
        ).order_by(MediaItem.added_date.asc()).all()
        
        to_delete = items[1:]
        for item in to_delete:
            db.session.delete(item)
            deleted_count += 1
            logger.info(f"Deleted duplicate movie: {item.title} ({item.year})")
    
    # Find duplicate series (same title)
    series_duplicates = db.session.query(
        MediaItem.title,
        func.count(MediaItem.id).label('count')
    ).filter(
        MediaItem.media_type == 'series'
    ).group_by(
        MediaItem.title
    ).having(
        func.count(MediaItem.id) > 1
    ).all()
    
    for dup in series_duplicates:
        items = MediaItem.query.filter_by(
            media_type='series',
            title=dup[0]
        ).order_by(MediaItem.added_date.asc()).all()
        
        to_delete = items[1:]
        for item in to_delete:
            db.session.delete(item)
            deleted_count += 1
            logger.info(f"Deleted duplicate series: {item.title}")
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'deleted': deleted_count,
        'message': f'Deleted {deleted_count} duplicate entries'
    })