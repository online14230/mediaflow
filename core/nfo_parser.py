# core/nfo_parser.py - Parse and write NFO files for metadata

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
import logging
from datetime import datetime
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class NFOParser:
    """Parse and write NFO files for movies and TV shows"""
    
    def __init__(self):
        pass
    
    def find_nfo_file(self, folder_path: str, media_type: str = 'movie') -> Optional[str]:
        """Find NFO file in folder"""
        if not os.path.exists(folder_path):
            return None
        
        if media_type == 'movie':
            # Look for movie.nfo first (preferred)
            movie_nfo = os.path.join(folder_path, 'movie.nfo')
            if os.path.exists(movie_nfo):
                return movie_nfo
            
            # Look for any .nfo file (excluding tvshow.nfo)
            for file in os.listdir(folder_path):
                if file.lower().endswith('.nfo') and file.lower() != 'tvshow.nfo':
                    return os.path.join(folder_path, file)
        else:
            # Look for tvshow.nfo
            tvshow_nfo = os.path.join(folder_path, 'tvshow.nfo')
            if os.path.exists(tvshow_nfo):
                return tvshow_nfo
        
        return None
    
    def parse_movie_nfo(self, nfo_path: str) -> Optional[Dict]:
        """Parse a movie NFO file and extract metadata"""
        if not os.path.exists(nfo_path):
            return None
        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            metadata = {
                'title': self._get_text(root, 'title'),
                'original_title': self._get_text(root, 'originaltitle'),
                'year': self._get_int(root, 'year'),
                'plot': self._get_text(root, 'plot'),
                'rating': self._get_float(root, 'rating'),
                'runtime': self._get_int(root, 'runtime'),
                'mpaa': self._get_text(root, 'mpaa'),
                'tagline': self._get_text(root, 'tagline'),
                'country': self._get_text(root, 'country'),
                'director': self._get_text(root, 'director'),
                'writers': self._get_multiple_text(root, 'writer'),
                'credits': self._get_multiple_text(root, 'credits'),
                'genres': self._get_multiple_text(root, 'genre'),
                'studios': self._get_multiple_text(root, 'studio'),
                'tags': self._get_multiple_text(root, 'tag'),
                'imdb_id': self._get_text(root, 'imdbid'),
                'tmdb_id': self._get_text(root, 'tmdbid'),
                'premiered': self._get_text(root, 'premiered'),
                'release_date': self._get_text(root, 'releasedate'),
                'critic_rating': self._get_text(root, 'criticrating'),
                'actors': self._get_actors(root),
                'trailers': self._get_multiple_text(root, 'trailer'),
                'poster_path': self._get_art_path(root, 'poster'),
                'fanart_path': self._get_art_path(root, 'fanart'),
                'date_added': self._get_text(root, 'dateadded')
            }
            
            # Clean up None values
            metadata = {k: v for k, v in metadata.items() if v is not None}
            return metadata
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse NFO file {nfo_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing NFO file {nfo_path}: {e}")
            return None
    
    def parse_tv_nfo(self, nfo_path: str) -> Optional[Dict]:
        """Parse a TV show NFO file (tvshow.nfo)"""
        if not os.path.exists(nfo_path):
            return None
        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            metadata = {
                'title': self._get_text(root, 'title'),
                'original_title': self._get_text(root, 'originaltitle'),
                'year': self._get_int(root, 'year'),
                'plot': self._get_text(root, 'plot'),
                'rating': self._get_float(root, 'rating'),
                'mpaa': self._get_text(root, 'mpaa'),
                'studio': self._get_text(root, 'studio'),
                'genres': self._get_multiple_text(root, 'genre'),
                'tags': self._get_multiple_text(root, 'tag'),
                'imdb_id': self._get_text(root, 'imdbid'),
                'tmdb_id': self._get_text(root, 'tmdbid'),
                'tvdb_id': self._get_text(root, 'tvdbid'),
                'premiered': self._get_text(root, 'premiered'),
                'status': self._get_text(root, 'status'),
                'actors': self._get_actors(root),
                'poster_path': self._get_art_path(root, 'poster'),
                'fanart_path': self._get_art_path(root, 'fanart'),
                'seasons': self._get_seasons(root)
            }
            
            metadata = {k: v for k, v in metadata.items() if v is not None}
            return metadata
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse NFO file {nfo_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing NFO file {nfo_path}: {e}")
            return None
    
    def write_movie_nfo(self, file_path: str, metadata: Dict) -> bool:
        """Write movie metadata to NFO file"""
        try:
            root = ET.Element('movie')
            
            self._add_text_element(root, 'title', metadata.get('title'))
            self._add_text_element(root, 'originaltitle', metadata.get('original_title'))
            if metadata.get('year'):
                self._add_text_element(root, 'year', str(metadata['year']))
            self._add_text_element(root, 'plot', metadata.get('overview') or metadata.get('plot'))
            if metadata.get('rating'):
                self._add_text_element(root, 'rating', str(metadata['rating']))
            if metadata.get('runtime'):
                self._add_text_element(root, 'runtime', str(metadata['runtime']))
            self._add_text_element(root, 'mpaa', metadata.get('mpaa'))
            self._add_text_element(root, 'tagline', metadata.get('tagline'))
            self._add_text_element(root, 'country', metadata.get('country'))
            self._add_text_element(root, 'director', metadata.get('director'))
            
            # Add multiple elements
            for writer in metadata.get('writers', []):
                self._add_text_element(root, 'writer', writer)
            
            for genre in metadata.get('genres', []):
                self._add_text_element(root, 'genre', genre)
            
            for studio in metadata.get('studios', []):
                self._add_text_element(root, 'studio', studio)
            
            for tag in metadata.get('tags', []):
                self._add_text_element(root, 'tag', tag)
            
            # IDs
            if metadata.get('imdb_id'):
                self._add_text_element(root, 'imdbid', metadata['imdb_id'])
            if metadata.get('tmdb_id'):
                self._add_text_element(root, 'tmdbid', str(metadata['tmdb_id']))
            
            # Dates
            if metadata.get('release_date'):
                self._add_text_element(root, 'releasedate', metadata['release_date'])
            
            # Actors
            for actor in metadata.get('actors', []):
                actor_elem = ET.SubElement(root, 'actor')
                self._add_text_element(actor_elem, 'name', actor.get('name'))
                self._add_text_element(actor_elem, 'role', actor.get('role'))
                self._add_text_element(actor_elem, 'type', 'Actor')
                if actor.get('order'):
                    self._add_text_element(actor_elem, 'sortorder', str(actor.get('order')))
            
            # Art
            if metadata.get('poster_path') or metadata.get('backdrop_path'):
                art_elem = ET.SubElement(root, 'art')
                if metadata.get('poster_path'):
                    self._add_text_element(art_elem, 'poster', metadata['poster_path'])
                if metadata.get('backdrop_path'):
                    self._add_text_element(art_elem, 'fanart', metadata['backdrop_path'])
            
            # Add date added
            self._add_text_element(root, 'dateadded', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Write to file
            tree = ET.ElementTree(root)
            tree.write(file_path, encoding='utf-8', xml_declaration=True)
            logger.info(f"Written NFO file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write NFO file: {e}")
            return False
    
    def _get_text(self, element, tag: str) -> Optional[str]:
        """Get text from XML element"""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return None
    
    def _get_int(self, element, tag: str) -> Optional[int]:
        """Get integer from XML element"""
        text = self._get_text(element, tag)
        if text:
            try:
                return int(text)
            except (ValueError, TypeError):
                pass
        return None
    
    def _get_float(self, element, tag: str) -> Optional[float]:
        """Get float from XML element"""
        text = self._get_text(element, tag)
        if text:
            try:
                return float(text)
            except (ValueError, TypeError):
                pass
        return None
    
    def _get_multiple_text(self, element, tag: str) -> List[str]:
        """Get text from multiple XML elements"""
        results = []
        for elem in element.findall(tag):
            if elem.text and elem.text.strip():
                results.append(elem.text.strip())
        return results
    
    def _get_actors(self, element) -> List[Dict]:
        """Get actors from XML element"""
        actors = []
        for actor_elem in element.findall('actor'):
            actor = {
                'name': self._get_text(actor_elem, 'name'),
                'role': self._get_text(actor_elem, 'role'),
                'type': self._get_text(actor_elem, 'type') or 'Actor',
                'order': self._get_int(actor_elem, 'sortorder') or len(actors)
            }
            if actor['name']:
                actors.append(actor)
        return actors
    
    def _get_art_path(self, element, art_type: str) -> Optional[str]:
        """Get art path from XML element"""
        art_elem = element.find('art')
        if art_elem is not None:
            path = self._get_text(art_elem, art_type)
            if path:
                return path
        return None
    
    def _get_seasons(self, element) -> List[Dict]:
        """Get seasons from XML element (for TV shows)"""
        seasons = []
        for season_elem in element.findall('season'):
            season = {
                'number': self._get_int(season_elem, 'number'),
                'episodes': []
            }
            if season['number']:
                for episode_elem in season_elem.findall('episode'):
                    episode = {
                        'number': self._get_int(episode_elem, 'episodenumber'),
                        'title': self._get_text(episode_elem, 'title'),
                        'plot': self._get_text(episode_elem, 'plot'),
                        'air_date': self._get_text(episode_elem, 'aired')
                    }
                    if episode['number']:
                        season['episodes'].append(episode)
                seasons.append(season)
        return seasons
    
    def _add_text_element(self, parent, tag: str, text: str):
        """Add text element to parent"""
        if text:
            elem = ET.SubElement(parent, tag)
            elem.text = str(text)
    
    def extract_youtube_id(self, trailer_url: str) -> Optional[str]:
        """Extract YouTube video ID from trailer URL"""
        if not trailer_url:
            return None
        
        # Handle plugin URLs
        if 'plugin://plugin.video.youtube/' in trailer_url:
            match = re.search(r'videoid=([a-zA-Z0-9_-]+)', trailer_url)
            if match:
                return match.group(1)
        
        # Handle direct YouTube URLs
        if 'youtube.com' in trailer_url or 'youtu.be' in trailer_url:
            patterns = [
                r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
                r'youtu\.be/([a-zA-Z0-9_-]+)',
                r'youtube\.com/embed/([a-zA-Z0-9_-]+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, trailer_url)
                if match:
                    return match.group(1)
        
        return None