# routes/library.py

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core import db, MediaItem
from core.config_manager import config_manager
from datetime import datetime
import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

library_bp = Blueprint('library', __name__)


def extract_movie_info(filename, folder_path):
    """Extract movie title and year from filename or folder name"""
    name = Path(filename).stem
    folder_name = Path(folder_path).name

    patterns = [
        r'^(.+?)\s*\((\d{4})\)',
        r'^(.+?)\.(\d{4})',
        r'^(.+?)\s+(\d{4})',
        r'^(.+?)[\.\s_-](\d{4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, folder_name, re.IGNORECASE)
        if match:
            title = match.group(1).replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
            year = match.group(2)
            title = re.sub(r'\s+', ' ', title)
            return {
                'title': title,
                'year': int(year),
                'filename': filename,
                'path': os.path.join(folder_path, filename),
                'folder_path': folder_path
            }

        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            title = match.group(1).replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
            year = match.group(2)
            title = re.sub(r'\s+', ' ', title)
            return {
                'title': title,
                'year': int(year),
                'filename': filename,
                'path': os.path.join(folder_path, filename),
                'folder_path': folder_path
            }

    title = folder_name.replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
    title = re.sub(r'\s+', ' ', title)

    remove_tags = ['1080p', '720p', '4k', 'bluray', 'webrip', 'web-dl', 'h264', 'x264', 'hevc', 'x265']
    for tag in remove_tags:
        title = re.sub(rf'\s*{tag}\s*', ' ', title, flags=re.IGNORECASE)
    title = title.strip()

    if not title or title == '':
        title = name.replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
        title = re.sub(r'\s+', ' ', title)

    return {
        'title': title,
        'year': None,
        'filename': filename,
        'path': os.path.join(folder_path, filename),
        'folder_path': folder_path
    }


def extract_tv_info(filename, folder_path, series_root_path):
    """Extract TV show title, season, episode from filename and folder structure - IMPROVED for single-letter shows"""
    name = Path(filename).stem
    parts = Path(folder_path).parts

    show_title = None
    season_num = None
    episode_num = None

    # FIRST: Get show title from series root folder (most reliable)
    if series_root_path:
        series_folder = Path(series_root_path).name
        # Remove year pattern like (2009) from folder name
        show_title = re.sub(r'\s*\(\d{4}\)\s*', ' ', series_folder)
        show_title = show_title.replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
        show_title = re.sub(r'\s+', ' ', show_title)
        show_title = show_title.strip()

        # Special handling for single-letter shows like "V"
        # Don't discard short titles - they could be valid show names
        if not show_title and len(series_folder) >= 1:
            show_title = series_folder.replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
            show_title = re.sub(r'\s*\(\d{4}\)\s*', ' ', show_title)
            show_title = show_title.strip()

        logger.info(f"Extracted show title from folder: '{show_title}'")

    # SECOND: Try to get from parent folder if series_root_path not available
    if not show_title and len(parts) >= 2:
        parent_folder = parts[-2]
        show_title = re.sub(r'\s*\(\d{4}\)\s*', ' ', parent_folder)
        show_title = show_title.replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
        show_title = re.sub(r'\s+', ' ', show_title)
        show_title = show_title.strip()

    # Extract season number from path
    for part in parts:
        season_match = re.search(r'[Ss]eason\s*(\d{1,2})', part, re.IGNORECASE)
        if season_match:
            season_num = int(season_match.group(1))
            break
        season_match = re.search(r'[Ss](\d{1,2})(?![Ee])', part, re.IGNORECASE)
        if season_match and not re.search(r'[Ee]', part):
            season_num = int(season_match.group(1))
            break
        if part.isdigit() and 1 <= int(part) <= 99:
            season_num = int(part)
            break

    if season_num is None:
        season_num = 1

    # Extract episode number from filename - IMPROVED patterns
    # Pattern 1: S01E02 (most common)
    ep_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', name, re.IGNORECASE)
    if ep_match:
        episode_num = int(ep_match.group(2))
        logger.debug(f"Found episode from SXXEYY: E{episode_num}")
    else:
        # Pattern 2: 1x02
        ep_match = re.search(r'(\d{1,2})x(\d{1,3})', name, re.IGNORECASE)
        if ep_match:
            episode_num = int(ep_match.group(2))
            logger.debug(f"Found episode from XXxYY: {episode_num}")
        else:
            # Pattern 3: Episode 02
            ep_match = re.search(r'[Ee]pisode\s*(\d{1,3})', name, re.IGNORECASE)
            if ep_match:
                episode_num = int(ep_match.group(1))
                logger.debug(f"Found episode from 'Episode XX': {episode_num}")
            else:
                # Pattern 4: E02 (standalone)
                ep_match = re.search(r'[Ee](\d{1,3})', name, re.IGNORECASE)
                if ep_match:
                    episode_num = int(ep_match.group(1))
                    logger.debug(f"Found episode from 'EXX': {episode_num}")
                else:
                    # Pattern 5: Numbers at end (e.g., "V.2009.S01E01")
                    ep_match = re.search(r'\.(\d{1,3})$', name)
                    if ep_match:
                        episode_num = int(ep_match.group(1))
                        logger.debug(f"Found episode from trailing number: {episode_num}")
                    else:
                        # Pattern 6: Number after episode indicator
                        ep_match = re.search(r'[Ee]pisode\.?(\d{1,3})', name, re.IGNORECASE)
                        if ep_match:
                            episode_num = int(ep_match.group(1))
                            logger.debug(f"Found episode from Episode pattern: {episode_num}")

    # If we found a show title and episode number, return the info
    if show_title and episode_num:
        if season_num is None:
            season_num = 1

        # Clean up show title
        show_title = re.sub(r'\s+', ' ', show_title).strip()
        show_title = re.sub(r'\s*-\s*$', '', show_title)
        show_title = re.sub(r'^\s*-\s*', '', show_title)

        # Remove any leftover parentheses content
        show_title = re.sub(r'\s*\([^)]*\)\s*', ' ', show_title)
        show_title = show_title.strip()

        # Special handling: If title is empty but we have a valid series folder
        if not show_title and series_root_path:
            show_title = Path(series_root_path).name
            show_title = re.sub(r'\s*\(\d{4}\)\s*', ' ', show_title)
            show_title = show_title.strip()

        if len(show_title) >= 1:  # Allow single-character show names like "V"
            logger.info(f"Successfully extracted - Show: '{show_title}', Season: {season_num}, Episode: {episode_num}")
            return {
                'title': show_title,
                'season': season_num,
                'episode': episode_num,
                'filename': filename,
                'path': os.path.join(folder_path, filename),
                'series_path': series_root_path if series_root_path else str(Path(folder_path).parent),
                'season_path': folder_path
            }

    logger.warning(f"Failed to extract - File: {filename}, Show title found: '{show_title}', Episode: {episode_num}")
    return None


def scan_movies_folder(folder_path):
    """Scan a folder for movie files"""
    movies = []
    video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.iso'}

    if not os.path.exists(folder_path):
        logger.error(f"Folder does not exist: {folder_path}")
        return movies

    logger.info(f"Scanning for movies in: {folder_path}")

    for root, dirs, files in os.walk(folder_path):
        if 'Season' in root or 'season' in root:
            continue

        skip_folders = ['extras', 'trailers', 'samples', 'subs', 'subtitles', 'covers']
        should_skip = any(skip in root.lower() for skip in skip_folders)
        if should_skip:
            continue

        for file in files:
            if Path(file).suffix.lower() in video_extensions and 'sample' not in file.lower():
                movie_info = extract_movie_info(file, root)
                if movie_info:
                    existing = any(m['title'] == movie_info['title'] for m in movies)
                    if not existing:
                        movies.append(movie_info)
                        logger.info(f"Found movie: {movie_info['title']}")

    logger.info(f"Total movies found: {len(movies)}")
    return movies


def scan_tv_folder(folder_path):
    """Scan a folder for TV episode files"""
    episodes = []
    video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}

    if not os.path.exists(folder_path):
        logger.error(f"Folder does not exist: {folder_path}")
        return episodes

    logger.info(f"Scanning for TV episodes in: {folder_path}")

    # First, list all series folders for debugging
    all_folders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
    logger.info(f"Found series folders: {all_folders}")

    for series_name in os.listdir(folder_path):
        series_path = os.path.join(folder_path, series_name)

        if not os.path.isdir(series_path):
            continue

        logger.info(f"Processing series: {series_name}")

        for root, dirs, files in os.walk(series_path):
            for file in files:
                if Path(file).suffix.lower() in video_extensions:
                    if 'sample' in file.lower():
                        continue

                    logger.info(f"Found video file: {file}")

                    episode_info = extract_tv_info(file, root, series_path)
                    if episode_info:
                        if not any(ep['path'] == episode_info['path'] for ep in episodes):
                            episodes.append(episode_info)
                            logger.info(f"[FOUND] Episode: {episode_info['title']} - S{episode_info['season']:02d}E{episode_info['episode']:02d} - {file}")
                    else:
                        logger.warning(f"Failed to parse: {file}")
                        logger.warning(f"  Path: {root}")
                        logger.warning(f"  Series path: {series_path}")

    logger.info(f"Total episodes found: {len(episodes)}")

    # Log unique shows found
    shows_found = {}
    for ep in episodes:
        title = ep['title']
        shows_found[title] = shows_found.get(title, 0) + 1

    logger.info(f"Shows found: {shows_found}")

    return episodes


@library_bp.route('/api/import-library', methods=['POST'])
@login_required
def import_library():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin required'}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})

        import_type = data.get('type')
        folder_path = data.get('path')
        clear_existing = data.get('clear_existing', False)

        if not folder_path:
            return jsonify({'success': False, 'error': 'No folder path provided'})

        if not os.path.exists(folder_path):
            return jsonify({'success': False, 'error': f'Folder not found: {folder_path}'})

        added_count = 0
        found_count = 0

        if import_type == 'movies':
            if clear_existing:
                deleted = MediaItem.query.filter_by(media_type='movie').delete()
                db.session.commit()
                logger.info(f"Cleared {deleted} existing movies")

            movies = scan_movies_folder(folder_path)
            found_count = len(movies)

            for movie in movies:
                existing = MediaItem.query.filter_by(
                    media_type='movie',
                    title=movie['title']
                ).first()

                if not existing:
                    poster_value = None
                    movie_folder = movie.get('folder_path', os.path.dirname(movie['path']))

                    for ext in ['.jpg', '.jpeg', '.png']:
                        for candidate in [
                            os.path.join(movie_folder, f'poster{ext}'),
                            os.path.join(movie_folder, f'folder{ext}'),
                            os.path.join(movie_folder, f'cover{ext}')
                        ]:
                            if os.path.exists(candidate):
                                poster_value = candidate
                                break
                        if poster_value:
                            break

                    new_movie = MediaItem(
                        media_type='movie',
                        title=movie['title'],
                        year=movie.get('year'),
                        overview=f'Imported from: {movie["filename"]}',
                        poster_path=poster_value,
                        added_date=datetime.utcnow()
                    )
                    new_movie.path = movie['path']
                    new_movie.file_path = movie['path']
                    new_movie.folder_path = movie.get('folder_path', os.path.dirname(movie['path']))

                    db.session.add(new_movie)
                    added_count += 1
                    logger.info(f"Added movie: {movie['title']}")

            db.session.commit()

        elif import_type == 'tv':
            if clear_existing:
                deleted = MediaItem.query.filter_by(media_type='series').delete()
                db.session.commit()
                logger.info(f"Cleared {deleted} existing series")

            episodes = scan_tv_folder(folder_path)
            found_count = len(episodes)

            # Group by show title
            shows = {}
            for episode in episodes:
                title = episode['title']
                if title not in shows:
                    shows[title] = []
                shows[title].append(episode)

            logger.info(f"Grouped into {len(shows)} unique shows: {list(shows.keys())}")

            for show_title, show_episodes in shows.items():
                existing = MediaItem.query.filter_by(
                    media_type='series',
                    title=show_title
                ).first()

                if not existing:
                    poster_value = None
                    series_path = show_episodes[0].get('series_path')

                    if series_path:
                        for ext in ['.jpg', '.jpeg', '.png']:
                            for candidate in [
                                os.path.join(series_path, f'poster{ext}'),
                                os.path.join(series_path, f'folder{ext}'),
                                os.path.join(series_path, f'show{ext}')
                            ]:
                                if os.path.exists(candidate):
                                    poster_value = candidate
                                    break
                            if poster_value:
                                break

                    new_show = MediaItem(
                        media_type='series',
                        title=show_title,
                        overview=f'Imported from library - {len(show_episodes)} episodes found',
                        poster_path=poster_value,
                        added_date=datetime.utcnow()
                    )
                    new_show.path = series_path if series_path else ''
                    new_show.file_path = series_path if series_path else ''
                    new_show.folder_path = series_path if series_path else ''

                    db.session.add(new_show)
                    added_count += 1
                    logger.info(f"Added series: {show_title} ({len(show_episodes)} episodes)")

            db.session.commit()

        return jsonify({
            'success': True,
            'found': found_count,
            'added': added_count,
            'message': f'Found {found_count} items, added {added_count}'
        })

    except Exception as e:
        logger.error(f"Import error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})