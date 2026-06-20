# core/real_torrent_indexers.py
import logging
import requests
import re
from typing import List, Dict, Optional
import json
import time

logger = logging.getLogger(__name__)

class RealTorrentIndexer:
    """Real torrent indexer using multiple sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        
        # Define indexers with their search methods
        self.indexers = [
            {'name': '1337x', 'enabled': True},
            {'name': 'EZTV', 'enabled': True},
            {'name': 'YTS', 'enabled': True},
            {'name': 'LimeTorrents', 'enabled': True},
            {'name': 'Nyaa', 'enabled': True},
            {'name': 'ThePirateBay', 'enabled': True},
            {'name': 'RuTracker', 'enabled': True},
            {'name': 'BTSOW', 'enabled': True},
        ]
    
    def search_movie(self, title: str, year: int = None, quality: str = '1080p') -> List[Dict]:
        """Search for movie torrents using multiple sources"""
        results = []
        
        # Build search query
        query = title
        if year:
            query = f"{title} {year}"
        
        logger.info(f"Searching for movie: {query}")
        
        # Try YTS (most reliable for movies)
        yts_results = self._search_yts(title, year)
        if yts_results:
            logger.info(f"Found {len(yts_results)} results from YTS")
            results.extend(yts_results)
        
        # Try 1337x
        if not results:
            x1337_results = self._search_1337x(query)
            if x1337_results:
                logger.info(f"Found {len(x1337_results)} results from 1337x")
                results.extend(x1337_results)
        
        # Try The Pirate Bay
        if not results:
            tpb_results = self._search_pirate_bay(query)
            if tpb_results:
                logger.info(f"Found {len(tpb_results)} results from The Pirate Bay")
                results.extend(tpb_results)
        
        # Try LimeTorrents
        if not results:
            lime_results = self._search_limetorrents(query)
            if lime_results:
                logger.info(f"Found {len(lime_results)} results from LimeTorrents")
                results.extend(lime_results)
        
        # Try RuTracker
        if not results:
            rutracker_results = self._search_rutracker(query)
            if rutracker_results:
                logger.info(f"Found {len(rutracker_results)} results from RuTracker")
                results.extend(rutracker_results)
        
        # Sort by seeders
        results.sort(key=lambda x: x.get('seeders', 0), reverse=True)
        
        return results
    
    def search_episode(self, series_title: str, season: int, episode: int, quality: str = '1080p') -> List[Dict]:
        """Search for TV episode torrents"""
        results = []
        
        query = f"{series_title} S{season:02d}E{episode:02d} {quality}"
        
        logger.info(f"Searching for episode: {query}")
        
        # Try EZTV (dedicated to TV shows)
        eztv_results = self._search_eztv(series_title, season, episode)
        if eztv_results:
            logger.info(f"Found {len(eztv_results)} results from EZTV")
            results.extend(eztv_results)
        
        # Try 1337x
        if not results:
            x1337_results = self._search_1337x(query)
            if x1337_results:
                logger.info(f"Found {len(x1337_results)} results from 1337x")
                results.extend(x1337_results)
        
        # Try The Pirate Bay
        if not results:
            tpb_results = self._search_pirate_bay(query)
            if tpb_results:
                logger.info(f"Found {len(tpb_results)} results from The Pirate Bay")
                results.extend(tpb_results)
        
        # Try Nyaa (anime and Asian content)
        if not results:
            nyaa_results = self._search_nyaa(query)
            if nyaa_results:
                logger.info(f"Found {len(nyaa_results)} results from Nyaa")
                results.extend(nyaa_results)
        
        # Sort by seeders
        results.sort(key=lambda x: x.get('seeders', 0), reverse=True)
        
        return results
    
    def search_series(self, series_title: str, year: int = None) -> List[Dict]:
        """Search for complete series torrents"""
        results = []
        
        query = f"{series_title} complete series"
        if year:
            query = f"{series_title} {year} complete"
        
        # Try 1337x
        x1337_results = self._search_1337x(query)
        if x1337_results:
            results.extend(x1337_results)
        
        # Try The Pirate Bay
        if not results:
            tpb_results = self._search_pirate_bay(query)
            if tpb_results:
                results.extend(tpb_results)
        
        return results
    
    def _search_yts(self, title: str, year: int = None) -> List[Dict]:
        """Search YTS API for movie torrents"""
        results = []
        
        try:
            yts_api_url = "https://yts.mx/api/v2/list_movies.json"
            
            params = {
                'query_term': title,
                'limit': 10,
                'sort_by': 'seeds',
                'order_by': 'desc'
            }
            if year:
                params['year'] = year
            
            response = self.session.get(yts_api_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'ok' and data.get('data', {}).get('movies'):
                    movies = data['data']['movies']
                    
                    for movie in movies[:5]:
                        torrents = movie.get('torrents', [])
                        for torrent in torrents:
                            if torrent.get('quality') in ['1080p', '720p', '2160p']:
                                results.append({
                                    'title': f"{movie.get('title')} ({movie.get('year')}) - {torrent.get('quality')} {torrent.get('type', '').upper()}",
                                    'size': torrent.get('size', 'Unknown'),
                                    'size_bytes': torrent.get('size_bytes', 0),
                                    'seeders': torrent.get('seeds', 0),
                                    'leechers': torrent.get('peers', 0),
                                    'magnet': torrent.get('url', ''),
                                    'indexer': 'YTS',
                                    'quality': torrent.get('quality', 'Unknown'),
                                    'source': torrent.get('type', 'BluRay').upper(),
                                    'hash': torrent.get('hash', '')
                                })
            else:
                logger.debug(f"YTS API returned status: {response.status_code}")
                
        except Exception as e:
            logger.debug(f"YTS search error: {e}")
        
        return results
    
    def _search_eztv(self, series_title: str, season: int, episode: int) -> List[Dict]:
        """Search EZTV for TV episode torrents"""
        results = []
        
        try:
            # EZTV API
            url = "https://eztvx.to/api/get-torrents"
            params = {'limit': 50}
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('torrents'):
                    series_lower = series_title.lower()
                    season_pattern = f"s{season:02d}e{episode:02d}"
                    season_pattern2 = f"s{season}e{episode}"
                    
                    for torrent in data.get('torrents', []):
                        torrent_title = torrent.get('title', '').lower()
                        
                        if series_lower in torrent_title and (season_pattern in torrent_title or season_pattern2 in torrent_title):
                            results.append({
                                'title': torrent.get('title', 'Unknown'),
                                'size': torrent.get('size', 'Unknown'),
                                'size_bytes': self._parse_size(torrent.get('size_str', '0 MB')),
                                'seeders': torrent.get('seeds', 0),
                                'leechers': torrent.get('peers', 0),
                                'magnet': torrent.get('magnet_url', ''),
                                'indexer': 'EZTV',
                                'quality': self._detect_quality(torrent.get('title', '')),
                                'source': 'WEB-DL',
                                'hash': torrent.get('hash', '')
                            })
            else:
                logger.debug(f"EZTV API returned status: {response.status_code}")
                
        except Exception as e:
            logger.debug(f"EZTV search error: {e}")
        
        return results
    
    def _search_1337x(self, query: str) -> List[Dict]:
        """Search 1337x for torrents"""
        results = []
        
        try:
            search_url = f"https://1337x.to/search/{query.replace(' ', '+')}/1/"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                # Extract torrent rows
                row_pattern = r'<tr[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>.*?<td[^>]*class="coll-2"[^>]*>(\d+)</td>.*?<td[^>]*class="coll-3"[^>]*>(\d+)</td>'
                matches = re.findall(row_pattern, response.text, re.DOTALL)
                
                for match in matches[:10]:
                    href, title, seeders, leechers = match
                    torrent_url = f"https://1337x.to{href}"
                    
                    magnet = self._get_magnet_from_page_1337x(torrent_url)
                    
                    if magnet:
                        results.append({
                            'title': title.strip(),
                            'size': 'Unknown',
                            'size_bytes': 0,
                            'seeders': int(seeders),
                            'leechers': int(leechers),
                            'magnet': magnet,
                            'indexer': '1337x',
                            'quality': self._detect_quality(title),
                            'source': self._detect_source(title)
                        })
            else:
                logger.debug(f"1337x returned {response.status_code}")
                
        except Exception as e:
            logger.debug(f"1337x search error: {e}")
        
        return results
    
    def _search_pirate_bay(self, query: str) -> List[Dict]:
        """Search The Pirate Bay for torrents"""
        results = []
        
        proxies = [
            'https://thepiratebay0.org',
            'https://piratebay.party',
            'https://thepiratebay10.org',
            'https://piratebay.live',
        ]
        
        for proxy in proxies:
            try:
                search_url = f"{proxy}/search/{query.replace(' ', '%20')}/0/99/0"
                
                response = self.session.get(search_url, timeout=10)
                
                if response.status_code == 200:
                    magnet_pattern = r'magnet:\?[^\s"\']+'
                    magnets = re.findall(magnet_pattern, response.text)
                    
                    title_pattern = r'<div class="detName">\s*<a href="[^"]+">([^<]+)</a>'
                    titles = re.findall(title_pattern, response.text)
                    
                    seed_pattern = r'<td align="right">(\d+)</td>'
                    seeds = re.findall(seed_pattern, response.text)
                    
                    if magnets and titles:
                        for i, magnet in enumerate(magnets[:10]):
                            title = titles[i] if i < len(titles) else query
                            seeders = int(seeds[i*2]) if i*2 < len(seeds) else 10
                            leechers = int(seeds[i*2+1]) if i*2+1 < len(seeds) else 5
                            
                            results.append({
                                'title': title,
                                'size': 'Unknown',
                                'size_bytes': 0,
                                'seeders': seeders,
                                'leechers': leechers,
                                'magnet': magnet,
                                'indexer': proxy.replace('https://', ''),
                                'quality': self._detect_quality(title),
                                'source': self._detect_source(title)
                            })
                        
                        if results:
                            break
                else:
                    logger.debug(f"Pirate Bay {proxy} returned {response.status_code}")
                    
            except Exception as e:
                logger.debug(f"Pirate Bay {proxy} error: {e}")
                continue
        
        return results
    
    def _search_limetorrents(self, query: str) -> List[Dict]:
        """Search LimeTorrents for torrents"""
        results = []
        
        try:
            search_url = f"https://www.limetorrents.lol/search/{query.replace(' ', '-')}/"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                magnet_pattern = r'magnet:\?[^\s"\']+'
                magnets = re.findall(magnet_pattern, response.text)
                
                title_pattern = r'<a class="tt-name" href="[^"]+">([^<]+)</a>'
                titles = re.findall(title_pattern, response.text)
                
                if magnets and titles:
                    for i, magnet in enumerate(magnets[:10]):
                        title = titles[i] if i < len(titles) else query
                        results.append({
                            'title': title,
                            'size': 'Unknown',
                            'size_bytes': 0,
                            'seeders': 15,
                            'leechers': 5,
                            'magnet': magnet,
                            'indexer': 'LimeTorrents',
                            'quality': self._detect_quality(title),
                            'source': self._detect_source(title)
                        })
            else:
                logger.debug(f"LimeTorrents returned {response.status_code}")
                
        except Exception as e:
            logger.debug(f"LimeTorrents search error: {e}")
        
        return results
    
    def _search_nyaa(self, query: str) -> List[Dict]:
        """Search Nyaa for torrents (anime/Asian content)"""
        results = []
        
        try:
            search_url = f"https://nyaa.si/?q={query.replace(' ', '+')}&c=0_0&f=0"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                magnet_pattern = r'magnet:\?[^\s"\']+'
                magnets = re.findall(magnet_pattern, response.text)
                
                title_pattern = r'<td colspan="2"><a href="/view/[^"]+">([^<]+)</a>'
                titles = re.findall(title_pattern, response.text)
                
                seed_pattern = r'<td class="text-center">(\d+)</td>'
                seeds = re.findall(seed_pattern, response.text)
                
                if magnets and titles:
                    for i, magnet in enumerate(magnets[:10]):
                        title = titles[i] if i < len(titles) else query
                        seeders = int(seeds[i*2]) if i*2 < len(seeds) else 10
                        leechers = int(seeds[i*2+1]) if i*2+1 < len(seeds) else 5
                        
                        results.append({
                            'title': title,
                            'size': 'Unknown',
                            'size_bytes': 0,
                            'seeders': seeders,
                            'leechers': leechers,
                            'magnet': magnet,
                            'indexer': 'Nyaa',
                            'quality': self._detect_quality(title),
                            'source': self._detect_source(title)
                        })
            else:
                logger.debug(f"Nyaa returned {response.status_code}")
                
        except Exception as e:
            logger.debug(f"Nyaa search error: {e}")
        
        return results
    
    def _search_rutracker(self, query: str) -> List[Dict]:
        """Search RuTracker for torrents (Russian tracker)"""
        results = []
        
        try:
            # RuTracker search
            search_url = f"https://rutracker.org/forum/tracker.php?nm={query.replace(' ', '+')}"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                magnet_pattern = r'magnet:\?[^\s"\']+'
                magnets = re.findall(magnet_pattern, response.text)
                
                if magnets:
                    for magnet in magnets[:5]:
                        results.append({
                            'title': query,
                            'size': 'Unknown',
                            'size_bytes': 0,
                            'seeders': 20,
                            'leechers': 10,
                            'magnet': magnet,
                            'indexer': 'RuTracker',
                            'quality': '1080p',
                            'source': 'Unknown'
                        })
            else:
                logger.debug(f"RuTracker returned {response.status_code}")
                
        except Exception as e:
            logger.debug(f"RuTracker search error: {e}")
        
        return results
    
    def _get_magnet_from_page_1337x(self, page_url: str) -> Optional[str]:
        """Extract magnet link from 1337x torrent page"""
        try:
            response = self.session.get(page_url, timeout=10)
            if response.status_code == 200:
                magnet_pattern = r'magnet:\?[^\s"\']+'
                magnets = re.findall(magnet_pattern, response.text)
                if magnets:
                    return magnets[0]
        except Exception as e:
            logger.debug(f"Error getting magnet from {page_url}: {e}")
        return None
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string to bytes"""
        try:
            size_str = size_str.upper().replace(',', '')
            if 'GB' in size_str:
                return int(float(size_str.replace('GB', '')) * 1024 * 1024 * 1024)
            elif 'MB' in size_str:
                return int(float(size_str.replace('MB', '')) * 1024 * 1024)
            elif 'KB' in size_str:
                return int(float(size_str.replace('KB', '')) * 1024)
            else:
                return 0
        except:
            return 0
    
    def _detect_quality(self, title: str) -> str:
        """Detect video quality from title"""
        title_upper = title.upper()
        if '4K' in title_upper or '2160P' in title_upper:
            return '4K'
        elif '1080P' in title_upper:
            return '1080p'
        elif '720P' in title_upper:
            return '720p'
        elif '480P' in title_upper:
            return '480p'
        else:
            return 'Unknown'
    
    def _detect_source(self, title: str) -> str:
        """Detect source type from title"""
        title_upper = title.upper()
        if 'BLURAY' in title_upper:
            return 'BluRay'
        elif 'WEB-DL' in title_upper or 'WEBDL' in title_upper:
            return 'WEB-DL'
        elif 'WEBRIP' in title_upper:
            return 'WEBRip'
        elif 'HDRIP' in title_upper:
            return 'HDRip'
        elif 'DVD' in title_upper:
            return 'DVD'
        else:
            return 'Unknown'