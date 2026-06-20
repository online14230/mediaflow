# core/ytdlp_player.py - Enhanced video player with popout support

import subprocess
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class EnhancedVideoPlayer:
    """Enhanced video player with popout support using yt-dlp and mpv"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.mpv_path = self._find_mpv()
    
    def _find_mpv(self) -> str:
        """Find mpv executable path"""
        # Check common locations
        common_paths = [
            "mpv.exe",
            "C:\\Program Files\\mpv\\mpv.exe",
            "C:\\mpv\\mpv.exe",
            "/usr/bin/mpv",
            "/usr/local/bin/mpv"
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return "mpv"  # Assume in PATH
    
    def play_with_mpv(self, file_path: str) -> bool:
        """Play video with mpv (popout player)"""
        try:
            subprocess.Popen([self.mpv_path, file_path], shell=True)
            logger.info(f"Launched mpv for {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to launch mpv: {e}")
            return False
    
    def play_with_mpv_network(self, url: str) -> bool:
        """Play network stream with mpv"""
        try:
            subprocess.Popen([self.mpv_path, url], shell=True)
            return True
        except Exception as e:
            logger.error(f"Failed to launch mpv for network stream: {e}")
            return False
    
    def get_popout_html(self, video_url: str) -> str:
        """Get HTML for popout player button"""
        return f'''
        <button class="btn btn-secondary" onclick="window.open('{video_url}', '_blank', 'width=1280,height=720')">
            <i class="bi bi-box-arrow-up-right"></i> Pop Out Player
        </button>
        '''