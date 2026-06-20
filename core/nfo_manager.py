# core/nfo_manager.py
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class NfoManager:
    """Reads and writes Kodi-style .nfo metadata files."""

    @staticmethod
    def find_nfo_file(movie_folder: str, imdb_id: str = None, tmdb_id: str = None) -> str | None:
        """Locate the .nfo file inside a movie folder.
        Typical names: movie.nfo, {imdb_id}.nfo, {tmdb_id}.nfo, or any .nfo file."""
        folder = Path(movie_folder)
        if not folder.is_dir():
            return None

        # Priority: imdbid.nfo, tmdbid.nfo, movie.nfo, any .nfo
        if imdb_id:
            candidate = folder / f"{imdb_id}.nfo"
            if candidate.exists():
                return str(candidate)
        if tmdb_id:
            candidate = folder / f"{tmdb_id}.nfo"
            if candidate.exists():
                return str(candidate)
        candidate = folder / "movie.nfo"
        if candidate.exists():
            return str(candidate)
        # fallback: first .nfo file
        for f in folder.glob("*.nfo"):
            return str(f)
        return None

    @staticmethod
    def parse_nfo(file_path: str) -> dict:
        """Parse Kodi .nfo XML into a dictionary compatible with MediaItem."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Helper to get text from element, return None if missing
            def get_text(tag):
                elem = root.find(tag)
                return elem.text.strip() if elem is not None and elem.text else None

            # Helper for multiple elements (writers, genres, studios)
            def get_list(tag):
                return [elem.text.strip() for elem in root.findall(tag) if elem.text]

            data = {
                'title': get_text('title'),
                'original_title': get_text('originaltitle'),
                'year': int(get_text('year')) if get_text('year') else None,
                'plot': get_text('plot'),
                'rating': float(get_text('rating')) if get_text('rating') else None,
                'runtime': int(get_text('runtime')) if get_text('runtime') else None,
                'mpaa': get_text('mpaa'),
                'imdb_id': get_text('imdbid'),
                'tmdb_id': get_text('tmdbid'),
                'director': get_text('director'),
                'tagline': get_text('tagline'),
                'country': get_text('country'),
                'premiered': get_text('premiered'),
                'studio': get_list('studio'),          # list
                'genre': get_list('genre'),            # list
                'tag': get_list('tag'),                # optional keywords
                'writer': get_list('writer'),          # writers
                'credits': get_list('credits'),        # credits
                'trailer': get_list('trailer'),        # URLs
                'art': {}                              # poster/fanart paths
            }

            # Artwork (poster, fanart)
            art_elem = root.find('art')
            if art_elem is not None:
                poster = art_elem.find('poster')
                fanart = art_elem.find('fanart')
                if poster is not None:
                    data['art']['poster'] = poster.text
                if fanart is not None:
                    data['art']['fanart'] = fanart.text

            # Actors (cast)
            actors = []
            for actor in root.findall('actor'):
                name_elem = actor.find('name')
                role_elem = actor.find('role')
                thumb_elem = actor.find('thumb')
                if name_elem is not None and name_elem.text:
                    actors.append({
                        'name': name_elem.text.strip(),
                        'role': role_elem.text.strip() if role_elem is not None else '',
                        'thumb': thumb_elem.text.strip() if thumb_elem is not None else ''
                    })
            data['actors'] = actors

            return data
        except Exception as e:
            logger.error(f"Failed to parse NFO {file_path}: {e}")
            return {}

    @staticmethod
    def write_nfo(media_item, nfo_path: str, artwork_dir: str = None):
        """Write MediaItem data to a Kodi-compatible .nfo file."""
        root = ET.Element('movie')
        ET.SubElement(root, 'title').text = media_item.title or ''
        if media_item.original_title:
            ET.SubElement(root, 'originaltitle').text = media_item.original_title
        ET.SubElement(root, 'plot').text = media_item.plot or ''
        ET.SubElement(root, 'rating').text = str(media_item.rating) if media_item.rating else '0'
        ET.SubElement(root, 'year').text = str(media_item.year) if media_item.year else ''
        ET.SubElement(root, 'runtime').text = str(media_item.runtime) if media_item.runtime else ''
        if media_item.mpaa:
            ET.SubElement(root, 'mpaa').text = media_item.mpaa
        if media_item.imdb_id:
            ET.SubElement(root, 'imdbid').text = media_item.imdb_id
        if media_item.tmdb_id:
            ET.SubElement(root, 'tmdbid').text = media_item.tmdb_id
        if media_item.director:
            ET.SubElement(root, 'director').text = media_item.director
        if media_item.tagline:
            ET.SubElement(root, 'tagline').text = media_item.tagline
        ET.SubElement(root, 'premiered').text = media_item.release_date or ''
        ET.SubElement(root, 'dateadded').text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Genres (as list)
        if media_item.genres:
            for genre in media_item.genres.split('|'):   # assuming stored as 'Action|Adventure'
                if genre.strip():
                    ET.SubElement(root, 'genre').text = genre.strip()

        # Studios
        if media_item.studio:   # might be a pipe-separated string
            for studio in media_item.studio.split('|'):
                if studio.strip():
                    ET.SubElement(root, 'studio').text = studio.strip()

        # Artwork – adjust paths relative to the .nfo location
        art_elem = ET.SubElement(root, 'art')
        if media_item.poster_path:
            poster_elem = ET.SubElement(art_elem, 'poster')
            poster_elem.text = media_item.poster_path
        if media_item.backdrop_path:
            fanart_elem = ET.SubElement(art_elem, 'fanart')
            fanart_elem.text = media_item.backdrop_path

        # Actors
        # (if you store cast as JSON in a 'cast' field, loop through)
        if hasattr(media_item, 'cast') and media_item.cast:
            import json
            cast_list = json.loads(media_item.cast) if isinstance(media_item.cast, str) else media_item.cast
            for idx, actor in enumerate(cast_list):
                actor_elem = ET.SubElement(root, 'actor')
                ET.SubElement(actor_elem, 'name').text = actor.get('name', '')
                ET.SubElement(actor_elem, 'role').text = actor.get('role', '')
                ET.SubElement(actor_elem, 'type').text = 'Actor'
                ET.SubElement(actor_elem, 'sortorder').text = str(idx)
                if actor.get('thumb'):
                    ET.SubElement(actor_elem, 'thumb').text = actor['thumb']

        # Write XML with proper header
        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')  # Python 3.9+
        with open(nfo_path, 'wb') as f:
            f.write(b'<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n')
            tree.write(f, encoding='utf-8')

        logger.info(f"Wrote NFO to {nfo_path}")