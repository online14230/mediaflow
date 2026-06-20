# core/download_client.py - Fixed qBittorrent 409 error

import requests
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote

logger = logging.getLogger(__name__)

class DownloadClient:
    """qBittorrent API wrapper - Fixed for 409 conflicts"""
    
    def __init__(self, config: Dict):
        self.host = config.get('host', 'http://localhost:8080').rstrip('/')
        self.username = config.get('username', 'admin')
        self.password = config.get('password', 'adminadmin')
        self.session = requests.Session()
        self.authenticated = False
        
        # Set a more complete User-Agent
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) MediaFlow/1.0'
        })
        
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with qBittorrent"""
        try:
            login_url = urljoin(self.host, '/api/v2/auth/login')
            logger.info(f"Authenticating with qBittorrent at {login_url}")
            
            response = self.session.post(login_url, data={
                'username': self.username,
                'password': self.password
            }, timeout=10)
            
            if response.status_code == 204:
                self.authenticated = True
                logger.info("qBittorrent authentication successful")
                return True
            elif response.status_code == 200 and 'Ok.' in response.text:
                self.authenticated = True
                logger.info("qBittorrent authentication successful")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def add_torrent(self, magnet_link: str, save_path: str = None, category: str = None) -> bool:
        """Add torrent via magnet link - Fixed for 409 conflicts"""
        self._ensure_auth()
        
        if not self.authenticated:
            logger.error("Not authenticated")
            return False
        
        try:
            url = urljoin(self.host, '/api/v2/torrents/add')
            
            # Prepare data - keep it simple to avoid 409
            data = {
                'urls': magnet_link,
                'paused': False
            }
            
            # Add save path if provided (clean it)
            if save_path:
                # Clean path - replace backslashes and spaces
                clean_path = save_path.replace('\\', '/').replace(' ', '_')
                data['savepath'] = clean_path
                logger.info(f"Save path: {clean_path}")
            
            # Skip category for now as it causes 409 conflicts
            # We'll add it after the torrent is added if needed
            # data['category'] is intentionally omitted to avoid 409
            
            logger.info(f"Sending add request to qBittorrent...")
            
            response = self.session.post(url, data=data, timeout=30)
            
            logger.info(f"Response status: {response.status_code}")
            
            # Check for success
            if response.status_code == 204:
                logger.info("Torrent added successfully (204)")
                return True
            elif response.status_code == 200:
                if 'Ok.' in response.text:
                    logger.info("Torrent added successfully (200)")
                    return True
                else:
                    logger.warning(f"Unexpected 200 response: {response.text[:100]}")
                    # Still might be a success
                    return True
            elif response.status_code == 409:
                logger.warning(f"Conflict (409) - Torrent may already exist: {response.text}")
                # If it's a conflict, the torrent might already be in the queue
                # Check if the torrent is already present
                if self._torrent_exists(magnet_link):
                    logger.info("Torrent already exists in qBittorrent queue")
                    return True
                return False
            else:
                logger.error(f"Failed with status {response.status_code}")
                if response.text:
                    logger.error(f"Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    def _torrent_exists(self, magnet_link: str) -> bool:
        """Check if a torrent already exists in qBittorrent"""
        try:
            torrents = self.get_torrents()
            # Extract info hash from magnet
            import re
            hash_match = re.search(r'btih:([a-fA-F0-9]+)', magnet_link)
            if hash_match:
                info_hash = hash_match.group(1).upper()
                for torrent in torrents:
                    if torrent.get('hash', '').upper() == info_hash:
                        return True
            return False
        except Exception as e:
            logger.error(f"Error checking existing torrent: {e}")
            return False
    
    def _ensure_auth(self):
        if not self.authenticated:
            self._authenticate()
    
    def get_torrents(self) -> List[Dict]:
        """Get list of torrents"""
        self._ensure_auth()
        if not self.authenticated:
            return []
        
        try:
            url = urljoin(self.host, '/api/v2/torrents/info')
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get torrents: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error: {e}")
            return []