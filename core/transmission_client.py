# core/transmission_client.py - Transmission Torrent Client Support (Fixed)

import logging
import requests
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

class TransmissionClient:
    """Transmission torrent client wrapper using JSON-RPC"""
    
    def __init__(self, config: Dict):
        self.host = config.get('host', 'http://localhost:9091').rstrip('/')
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.session = requests.Session()
        self.session_id = None
        
        # Set authentication if provided
        if self.username and self.password:
            self.session.auth = (self.username, self.password)
        
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with Transmission and get session ID"""
        try:
            url = f"{self.host}/transmission/rpc"
            
            # First request to get session ID (will fail with 409)
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 409:
                # Extract session ID from headers
                self.session_id = response.headers.get('X-Transmission-Session-Id')
                self.session.headers.update({'X-Transmission-Session-Id': self.session_id})
                logger.info("Transmission session established")
                return True
            elif response.status_code == 200:
                # Already authenticated
                logger.info("Transmission already authenticated")
                return True
            else:
                logger.error(f"Unexpected response: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def _ensure_auth(self):
        """Ensure we have a valid session"""
        if not self.session_id:
            self._authenticate()
    
    def _rpc_call(self, method: str, arguments: Dict = None) -> Optional[Dict]:
        """Make JSON-RPC call to Transmission"""
        self._ensure_auth()
        
        url = f"{self.host}/transmission/rpc"
        payload = {
            'method': method,
            'arguments': arguments or {}
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            
            # Handle session expiration
            if response.status_code == 409:
                self.session_id = response.headers.get('X-Transmission-Session-Id')
                self.session.headers.update({'X-Transmission-Session-Id': self.session_id})
                response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('result') == 'success':
                    return data.get('arguments', {})
                else:
                    logger.error(f"RPC error: {data.get('result')}")
                    return None
            else:
                logger.error(f"HTTP error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"RPC call error: {e}")
            return None
    
    def add_torrent(self, magnet_link: str, download_dir: str = None, paused: bool = False) -> bool:
        """Add torrent via magnet link"""
        self._ensure_auth()
        
        if not self.session_id:
            logger.error("No Transmission session ID")
            return False
        
        arguments = {'filename': magnet_link}
        
        if download_dir:
            # Convert Windows path to forward slashes
            download_dir = download_dir.replace('\\', '/')
            arguments['download-dir'] = download_dir
        
        if paused:
            arguments['paused'] = True
        
        logger.info(f"Adding torrent to Transmission: {magnet_link[:100]}...")
        logger.info(f"Download directory: {download_dir}")
        
        result = self._rpc_call('torrent-add', arguments)
        
        if result is not None:
            logger.info("Torrent added successfully to Transmission")
            return True
        else:
            logger.error("Failed to add torrent to Transmission")
            return False
    
    def get_torrents(self) -> List[Dict]:
        """Get list of all torrents"""
        result = self._rpc_call('torrent-get', {'fields': ['id', 'name', 'percentDone', 'status', 'totalSize']})
        if result:
            return result.get('torrents', [])
        return []
    
    def remove_torrent(self, torrent_id: int, delete_data: bool = False) -> bool:
        """Remove torrent by ID"""
        result = self._rpc_call('torrent-remove', {
            'ids': [torrent_id],
            'delete-local-data': delete_data
        })
        return result is not None
    
    def start_torrent(self, torrent_id: int) -> bool:
        """Start/resume torrent"""
        result = self._rpc_call('torrent-start', {'ids': [torrent_id]})
        return result is not None
    
    def stop_torrent(self, torrent_id: int) -> bool:
        """Stop/pause torrent"""
        result = self._rpc_call('torrent-stop', {'ids': [torrent_id]})
        return result is not None