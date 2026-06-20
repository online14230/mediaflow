# routes/api/metadata_routes.py
import os
import logging
from flask import request, jsonify
from flask_login import login_required, current_user

from core import db, MediaItem
from core.config_manager import config_manager
from .core_routes import get_services
from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/api/movies')
@login_required
def get_movies():
    """Get movies, optionally filter by missing metadata"""
    missing_metadata = request.args.get('missing_metadata', 'false') == 'true'
    
    if missing_metadata:
        movies = MediaItem.query.filter_by(media_type='movie').all()
        result = []
        for movie in movies:
            missing = []
            if not movie.poster_path:
                missing.append('poster')
            if not movie.overview or len(movie.overview) < 50:
                missing.append('overview')
            if not movie.backdrop_path:
                missing.append('backdrop')
            if missing:
                result.append({
                    'id': movie.id,
                    'title': movie.title,
                    'year': movie.year,
                    'missing_fields': missing
                })
        return jsonify({'movies': result})
    
    page = request.args.get('page', 1, type=int)
    per_page = config_manager.get('ui.items_per_page', 20)
    movies = MediaItem.query.filter_by(media_type='movie').order_by(
        MediaItem.added_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'movies': [{
            'id': m.id,
            'title': m.title,
            'year': m.year,
            'poster_path': m.poster_path
        } for m in movies.items],
        'total': movies.total,
        'page': movies.page,
        'pages': movies.pages
    })


@api_bp.route('/api/series')
@login_required
def get_series():
    """Get TV series, optionally filter by missing metadata"""
    missing_metadata = request.args.get('missing_metadata', 'false') == 'true'
    
    if missing_metadata:
        series_list = MediaItem.query.filter_by(media_type='series').all()
        result = []
        for series in series_list:
            missing = []
            if not series.poster_path:
                missing.append('poster')
            if not series.overview or len(series.overview) < 50:
                missing.append('overview')
            if not series.backdrop_path:
                missing.append('backdrop')
            if missing:
                result.append({
                    'id': series.id,
                    'title': series.title,
                    'year': series.year,
                    'missing_fields': missing
                })
        return jsonify({'series': result})
    
    page = request.args.get('page', 1, type=int)
    per_page = config_manager.get('ui.items_per_page', 20)
    series_list = MediaItem.query.filter_by(media_type='series').order_by(
        MediaItem.added_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'series': [{
            'id': s.id,
            'title': s.title,
            'year': s.year,
            'poster_path': s.poster_path
        } for s in series_list.items],
        'total': series_list.total,
        'page': series_list.page,
        'pages': series_list.pages
    })


@api_bp.route('/api/youtube/trailer')
@login_required
def get_youtube_trailer():
    """Get YouTube trailer for media"""
    title = request.args.get('title', '')
    year = request.args.get('year', None)
    media_type = request.args.get('type', 'movie')
    
    services = get_services()
    trailers = services['youtube_fetcher'].search_trailer(title, year, media_type)
    
    return jsonify({'trailers': trailers})


@api_bp.route('/api/metadata/fix-movie/<int:movie_id>', methods=['POST'])
@login_required
def fix_movie_metadata(movie_id):
    """Fix missing metadata for a specific movie"""
    movie = MediaItem.query.get_or_404(movie_id)
    services = get_services()
    
    search_results = services['metadata_fixer'].search_movie(movie.title, movie.year)
    
    if not search_results:
        return jsonify({'success': False, 'error': 'No matching movies found. Check TMDB API key in settings.'})
    
    best_match = search_results[0]
    details = services['metadata_fixer'].get_movie_details(best_match['id'])
    
    if details:
        if details.get('title'):
            movie.title = details['title']
        if details.get('year'):
            movie.year = int(details['year']) if details['year'].isdigit() else movie.year
        if details.get('overview'):
            movie.overview = details['overview']
        if details.get('poster_path'):
            movie.poster_path = details['poster_path']
        if details.get('backdrop_path'):
            movie.backdrop_path = details['backdrop_path']
        if details.get('rating'):
            movie.rating = details['rating']
        if details.get('runtime'):
            movie.runtime = details['runtime']
        if details.get('director'):
            movie.director = details['director']
        if details.get('genres'):
            movie.genres = str(details['genres'])
        
        db.session.commit()
        
        if details.get('poster_path') and movie.path:
            poster_path = os.path.join(movie.path, 'poster.jpg')
            services['metadata_fixer'].download_poster(details['poster_path'], poster_path)
        
        return jsonify({'success': True, 'message': f'Updated metadata for {movie.title}'})
    
    return jsonify({'success': False, 'error': 'Failed to fetch details from TMDB'})


@api_bp.route('/api/metadata/fix-series/<int:series_id>', methods=['POST'])
@login_required
def fix_series_metadata(series_id):
    """Fix missing metadata for a specific TV series"""
    series = MediaItem.query.get_or_404(series_id)
    services = get_services()
    
    search_results = services['metadata_fixer'].search_tv_series(series.title, series.year)
    
    if not search_results:
        return jsonify({'success': False, 'error': 'No matching series found. Check TMDB API key in settings.'})
    
    best_match = search_results[0]
    details = services['metadata_fixer'].get_series_details(best_match['id'])
    
    if details:
        if details.get('title'):
            series.title = details['title']
        if details.get('year'):
            series.year = int(details['year']) if details['year'].isdigit() else series.year
        if details.get('overview'):
            series.overview = details['overview']
        if details.get('poster_path'):
            series.poster_path = details['poster_path']
        if details.get('backdrop_path'):
            series.backdrop_path = details['backdrop_path']
        if details.get('rating'):
            series.rating = details['rating']
        if details.get('genres'):
            series.genres = str(details['genres'])
        
        db.session.commit()
        
        if details.get('poster_path') and series.path:
            poster_path = os.path.join(series.path, 'poster.jpg')
            services['metadata_fixer'].download_poster(details['poster_path'], poster_path)
        
        return jsonify({'success': True, 'message': f'Updated metadata for {series.title}'})
    
    return jsonify({'success': False, 'error': 'Failed to fetch details from TMDB'})


@api_bp.route('/api/metadata/search', methods=['POST'])
@login_required
def search_metadata():
    """Search for matching movies/series"""
    data = request.json
    media_type = data.get('type')
    title = data.get('title')
    year = data.get('year')
    services = get_services()
    
    if media_type == 'movie':
        results = services['metadata_fixer'].search_movie(title, year)
    else:
        results = services['metadata_fixer'].search_tv_series(title, year)
    
    if not results and not services['metadata_fixer'].tmdb_api_key:
        return jsonify({
            'results': [],
            'warning': 'No TMDB API key configured. Add your API key in Settings to enable metadata fetching.'
        })
    
    return jsonify({'results': results})


@api_bp.route('/api/metadata/apply', methods=['POST'])
@login_required
def apply_metadata():
    """Apply selected metadata to media item"""
    data = request.json
    media_id = data.get('media_id')
    media_type = data.get('media_type')
    external_id = data.get('external_id')
    services = get_services()
    
    media_item = MediaItem.query.get_or_404(media_id)
    
    if media_type == 'movie':
        details = services['metadata_fixer'].get_movie_details(external_id)
    else:
        details = services['metadata_fixer'].get_series_details(external_id)
    
    if details:
        if details.get('title'):
            media_item.title = details['title']
        if details.get('year'):
            media_item.year = int(details['year']) if details['year'].isdigit() else media_item.year
        if details.get('overview'):
            media_item.overview = details['overview']
        if details.get('poster_path'):
            media_item.poster_path = details['poster_path']
        if details.get('backdrop_path'):
            media_item.backdrop_path = details['backdrop_path']
        if details.get('rating'):
            media_item.rating = details['rating']
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Metadata updated'})
    
    return jsonify({'success': False, 'error': 'Failed to apply metadata'})


@api_bp.route('/api/metadata/fix-missing', methods=['POST'])
@login_required
def fix_missing_metadata():
    """Scan and fix all missing metadata"""
    data = request.json
    media_type = data.get('type')
    services = get_services()
    
    if media_type == 'movie':
        items = MediaItem.query.filter_by(media_type='movie').all()
    else:
        items = MediaItem.query.filter_by(media_type='series').all()
    
    fixed = 0
    failed = 0
    skipped = 0
    
    for item in items:
        if item.poster_path and item.overview and len(item.overview) > 50:
            skipped += 1
            continue
        
        try:
            if media_type == 'movie':
                results = services['metadata_fixer'].search_movie(item.title, item.year)
            else:
                results = services['metadata_fixer'].search_tv_series(item.title, item.year)
            
            if results:
                best_match = results[0]
                if media_type == 'movie':
                    details = services['metadata_fixer'].get_movie_details(best_match['id'])
                else:
                    details = services['metadata_fixer'].get_series_details(best_match['id'])
                
                if details:
                    if details.get('poster_path'):
                        item.poster_path = details['poster_path']
                    if details.get('backdrop_path'):
                        item.backdrop_path = details['backdrop_path']
                    if details.get('overview'):
                        item.overview = details['overview']
                    if details.get('rating'):
                        item.rating = details['rating']
                    db.session.commit()
                    fixed += 1
                    logger.info(f"Fixed metadata for {item.title}")
                else:
                    failed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Failed to fix {item.title}: {e}")
            failed += 1
    
    return jsonify({
        'fixed': fixed,
        'failed': failed,
        'skipped': skipped,
        'total': len(items),
        'message': f'Fixed {fixed} items, failed {failed}, skipped {skipped}'
    })


@api_bp.route('/api/series/<int:show_id>/search', methods=['POST'])
@login_required
def search_episode(show_id):
    """Search for a specific episode torrent"""
    data = request.json
    show = MediaItem.query.get_or_404(show_id)
    season = data.get('season')
    episode = data.get('episode')
    services = get_services()
    results = services['media_searcher'].search_episode(show.title, season, episode)
    return jsonify({'results': results})


@api_bp.route('/api/series/<int:show_id>/search-missing', methods=['POST'])
@login_required
def search_missing_episodes(show_id):
    """Search for all missing episodes of a series"""
    from core.episode_manager import EpisodeManager
    show = MediaItem.query.get_or_404(show_id)
    episode_manager = EpisodeManager(config_manager)
    if not show.path or not os.path.exists(show.path):
        return jsonify({'found': 0, 'added': 0})
    missing = episode_manager.find_missing_episodes(show.path)
    services = get_services()
    found_count = 0
    for ep in missing:
        results = services['media_searcher'].search_episode(show.title, ep['season'], ep['episode'])
        found_count += len(results)
    return jsonify({'found': found_count, 'added': 0})


@api_bp.route('/api/series/<int:show_id>/search-episodes', methods=['POST'])
@login_required
def search_series_episodes(show_id):
    """Search for episodes across seasons"""
    show = MediaItem.query.get_or_404(show_id)
    data = request.json
    quality = data.get('quality', '1080p')
    season = data.get('season')
    
    services = get_services()
    
    if season:
        results = []
        for episode_num in range(1, 25):
            episode_results = services['media_searcher'].search_episode(
                show.title, season, episode_num, quality
            )
            if episode_results:
                results.append({
                    'season': season,
                    'episode': episode_num,
                    'results': episode_results
                })
        return jsonify({'results': results})
    else:
        all_results = {}
        for season_num in range(1, 6):
            season_results = []
            for episode_num in range(1, 25):
                episode_results = services['media_searcher'].search_episode(
                    show.title, season_num, episode_num, quality
                )
                if episode_results:
                    season_results.append({
                        'episode': episode_num,
                        'results': episode_results
                    })
            if season_results:
                all_results[season_num] = season_results
        return jsonify({'results': all_results})