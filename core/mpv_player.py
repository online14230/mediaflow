# core/mpv_player.py
import subprocess
import os
import logging
import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional, List
from flask import Response

logger = logging.getLogger(__name__)

class MPVPlayer:
    """Handles MPV video playback and streaming with Jellyfin-like features"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.mpv_path = self._find_mpv()
        self.websocket_clients = {}
        self.active_streams = {}
        
    def _find_mpv(self) -> str:
        """Find mpv executable path - Enhanced for common Windows locations"""
        # Common Windows installation paths
        common_paths = [
            # Current directory
            "mpv.exe",
            "mpv.com",
            # Program Files
            "C:\\Program Files\\mpv\\mpv.exe",
            "C:\\Program Files\\mpv\\x86_64\\mpv.exe",
            "C:\\Program Files\\mpv\\i686\\mpv.exe",
            "C:\\Program Files (x86)\\mpv\\mpv.exe",
            # User installed locations
            os.path.expanduser("~\\mpv\\mpv.exe"),
            os.path.expanduser("~\\Desktop\\mpv\\mpv.exe"),
            # Portable installations
            "C:\\mpv\\mpv.exe",
            "C:\\mpv\\x86_64\\mpv.exe",
            "D:\\mpv\\mpv.exe",
            # Chocolatey install location
            "C:\\ProgramData\\chocolatey\\lib\\mpv\\tools\\mpv.exe",
            # Scoop install location
            os.path.expanduser("~\\scoop\\apps\\mpv\\current\\mpv.exe"),
            # Windows Package Manager
            "C:\\Users\\%USERNAME%\\AppData\\Local\\Microsoft\\WinGet\\Packages\\mpv.*\\mpv.exe",
            # Linux/Unix paths
            "/usr/bin/mpv",
            "/usr/local/bin/mpv",
            "/snap/bin/mpv"
        ]
        
        for path in common_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                logger.info(f"Found MPV at: {expanded_path}")
                return expanded_path
        
        # Check if in PATH
        try:
            result = subprocess.run(['where', 'mpv'], capture_output=True, timeout=5, shell=True)
            if result.returncode == 0:
                mpv_path = result.stdout.decode().strip().split('\n')[0]
                if os.path.exists(mpv_path):
                    logger.info(f"Found MPV in PATH at: {mpv_path}")
                    return mpv_path
        except:
            pass
        
        try:
            result = subprocess.run(['mpv', '--version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                logger.info("Found MPV in system PATH")
                return "mpv"
        except:
            pass
            
        logger.warning("MPV not found in common locations. Will use fallback HTML5 player.")
        logger.warning("Download MPV from https://mpv.io/installation/")
        return None
    
    def is_available(self) -> bool:
        """Check if MPV is available"""
        return self.mpv_path is not None and (os.path.exists(self.mpv_path) if self.mpv_path != "mpv" else True)
    
    def get_player_html(self, video_url: str, media_id: int, media_type: str, 
                        title: str, subtitles: List[str] = None) -> str:
        """Generate HTML for MPV player (Jellyfin-style)"""
        if not self.is_available():
            return self._get_fallback_player_html(video_url)
        
        subtitle_tracks = ""
        if subtitles:
            for i, sub in enumerate(subtitles):
                subtitle_tracks += f'''
                <track kind="subtitles" src="{sub}" srclang="eng" label="Subtitle {i+1}" default="{i==0}">
                '''
        
        # Encode video URL for JavaScript
        safe_video_url = video_url.replace("'", "\\'")
        
        return f'''
        <div id="mpv-player-container" style="position: relative; width: 100%; background: #000; border-radius: 10px;">
            <video id="mpv-player" 
                   class="w-100" 
                   controls 
                   autoplay 
                   style="background: #000; border-radius: 10px; max-height: 70vh;"
                   data-media-id="{media_id}"
                   data-media-type="{media_type}"
                   data-title="{title}">
                <source src="{video_url}" type="video/mp4">
                <source src="{video_url}" type="video/x-matroska">
                <source src="{video_url}" type="video/webm">
                {subtitle_tracks}
                Your browser does not support the video tag.
            </video>
            <div class="mpv-controls" style="position: absolute; bottom: 10px; right: 10px; z-index: 1000;">
                <button class="btn btn-secondary btn-sm" onclick="openMPVPopout()" title="Open in MPV (Popout)">
                    <i class="bi bi-box-arrow-up-right"></i> MPV Popout
                </button>
                <button class="btn btn-info btn-sm ms-1" onclick="checkMPVInstall()" title="MPV Installation Help">
                    <i class="bi bi-question-circle"></i>
                </button>
            </div>
        </div>
        
        <script>
        let mpvPlayer = document.getElementById('mpv-player');
        let mpvSaveInterval = null;
        let mpvLastPosition = 0;
        
        function openMPVPopout() {{
            const videoUrl = "{safe_video_url}";
            const title = "{title}";
            if (videoUrl) {{
                window.open(`/api/mpv/popout?url=${{encodeURIComponent(videoUrl)}}&title=${{encodeURIComponent(title)}}`, '_blank', 'width=1280,height=720,toolbar=yes,menubar=yes,location=yes');
            }}
        }}
        
        function checkMPVInstall() {{
            fetch('/api/mpv/status')
                .then(response => response.json())
                .then(data => {{
                    if (data.available) {{
                        alert('✓ MPV Player is installed and ready to use!\\n\\nUse the "MPV Popout" button for dedicated player window.');
                    }} else {{
                        alert('✗ MPV Player not found\\n\\nPlease install MPV from:\\nhttps://mpv.io/installation/\\n\\nAfter installation, restart MediaFlow.');
                    }}
                }});
        }}
        
        // Save playback position
        if (mpvSaveInterval) clearInterval(mpvSaveInterval);
        mpvSaveInterval = setInterval(() => {{
            if (mpvPlayer && mpvPlayer.currentTime && !mpvPlayer.paused) {{
                const currentPos = Math.floor(mpvPlayer.currentTime);
                if (currentPos !== mpvLastPosition) {{
                    mpvLastPosition = currentPos;
                    fetch('/api/watch/progress', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            media_id: {media_id},
                            media_type: '{media_type}',
                            position: currentPos,
                            duration: Math.floor(mpvPlayer.duration || 0)
                        }})
                    }}).catch(err => console.log('Progress save failed'));
                }}
            }}
        }}, 5000);
        
        // Restore playback position
        window.addEventListener('load', () => {{
            const savedTime = localStorage.getItem(`mpv_position_${{media_id}}`);
            if (savedTime && mpvPlayer) {{
                mpvPlayer.currentTime = parseFloat(savedTime);
            }}
        }});
        
        // Save position on page unload
        window.addEventListener('beforeunload', () => {{
            if (mpvPlayer && mpvPlayer.currentTime) {{
                localStorage.setItem(`mpv_position_${{media_id}}`, mpvPlayer.currentTime);
            }}
        }});
        
        // Handle video errors
        mpvPlayer.onerror = function(e) {{
            console.error('MPV player error:', e);
            const errorMessage = mpvPlayer.error ? mpvPlayer.error.message : 'Unknown error';
            if (errorMessage.includes('no video') || errorMessage.includes('codec')) {{
                const errorDiv = document.createElement('div');
                errorDiv.className = 'alert alert-warning mt-2';
                errorDiv.innerHTML = `
                    <i class="bi bi-exclamation-triangle"></i>
                    HTML5 player couldn't play this video format. 
                    <button class="btn btn-sm btn-primary" onclick="openMPVPopout()">
                        Open in MPV Player Instead
                    </button>
                    <hr>
                    <small>Tip: Install MPV for better codec support.</small>
                `;
                mpvPlayer.parentNode.appendChild(errorDiv);
            }}
        }};
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {{
            if (!mpvPlayer) return;
            
            // Space: Play/Pause
            if (e.code === 'Space') {{
                e.preventDefault();
                if (mpvPlayer.paused) {{
                    mpvPlayer.play();
                }} else {{
                    mpvPlayer.pause();
                }}
            }}
            // Left arrow: -10 seconds
            else if (e.code === 'ArrowLeft') {{
                e.preventDefault();
                mpvPlayer.currentTime = Math.max(0, mpvPlayer.currentTime - 10);
            }}
            // Right arrow: +10 seconds
            else if (e.code === 'ArrowRight') {{
                e.preventDefault();
                mpvPlayer.currentTime = Math.min(mpvPlayer.duration, mpvPlayer.currentTime + 10);
            }}
            // Up arrow: Volume up
            else if (e.code === 'ArrowUp') {{
                e.preventDefault();
                mpvPlayer.volume = Math.min(1, mpvPlayer.volume + 0.1);
            }}
            // Down arrow: Volume down
            else if (e.code === 'ArrowDown') {{
                e.preventDefault();
                mpvPlayer.volume = Math.max(0, mpvPlayer.volume - 0.1);
            }}
            // F: Fullscreen
            else if (e.code === 'KeyF') {{
                e.preventDefault();
                if (mpvPlayer.requestFullscreen) {{
                    mpvPlayer.requestFullscreen();
                }}
            }}
            // M: Mute
            else if (e.code === 'KeyM') {{
                e.preventDefault();
                mpvPlayer.muted = !mpvPlayer.muted;
            }}
        }});
        </script>
        '''
    
    def _get_fallback_player_html(self, video_url: str) -> str:
        """Fallback HTML5 player when MPV is not available with install instructions"""
        return f'''
        <div id="fallback-player">
            <video id="videoPlayer" class="w-100" controls autoplay style="background: #000; border-radius: 10px; max-height: 70vh;">
                <source src="{video_url}" type="video/mp4">
                <source src="{video_url}" type="video/x-matroska">
                <source src="{video_url}" type="video/webm">
                Your browser does not support the video tag.
            </video>
            <div class="alert alert-warning mt-2">
                <i class="bi bi-exclamation-triangle"></i>
                <strong>MPV Player not found</strong><br>
                For better playback performance and codec support, install MPV:
                <ul class="mt-2">
                    <li><a href="https://mpv.io/installation/" target="_blank">Download MPV</a></li>
                    <li>Extract to <code>C:\\Program Files\\mpv\\</code></li>
                    <li>Restart MediaFlow</li>
                </ul>
                <button class="btn btn-sm btn-primary mt-2" onclick="window.open('https://mpv.io/installation/', '_blank')">
                    <i class="bi bi-download"></i> Download MPV
                </button>
            </div>
        </div>
        '''
    
    def launch_mpv_popout(self, video_url: str, title: str) -> bool:
        """Launch MPV in a separate window (popout player)"""
        if not self.is_available():
            logger.error("MPV not available for popout")
            return False
        
        try:
            # Start MPV with the video URL
            cmd = [self.mpv_path, video_url, f'--title={title}', '--keepaspect=yes', '--border=yes', '--really-quiet']
            
            # Use subprocess.Popen to launch without blocking
            if os.name == 'nt':  # Windows
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            else:  # Linux/Mac
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Launched MPV popout for: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to launch MPV popout: {e}")
            return False
    
    def generate_hls_stream(self, file_path: str) -> Response:
        """Generate HLS stream for better compatibility (optional)"""
        # This would use ffmpeg to create HLS segments
        # For now, return direct file stream
        from flask import send_file
        return send_file(file_path, conditional=True)


class MPVStreamHandler:
    """Handles video streaming with range support for MPV"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.chunk_size = 1024 * 1024  # 1MB chunks
    
    def stream_video_with_mpv(self, file_path: str, media_id: int = None):
        """Stream video with support for seeking (required for MPV)"""
        from flask import request, Response
        import mimetypes
        
        if not os.path.exists(file_path):
            return "File not found", 404
        
        file_size = os.path.getsize(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or 'video/mp4'
        
        # Handle MKV files - browser might not support them directly
        if file_path.endswith('.mkv'):
            mime_type = 'video/x-matroska'
        
        range_header = request.headers.get('Range', None)
        
        if range_header:
            # Parse range header (MPV requires this for seeking)
            try:
                byte_range = range_header.strip().split('=')[1]
                start, end = byte_range.split('-')
                start = int(start)
                end = int(end) if end else file_size - 1
                content_length = end - start + 1
                
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    data = f.read(content_length)
                
                response = Response(data, status=206, mimetype=mime_type)
                response.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
                response.headers.add('Accept-Ranges', 'bytes')
                response.headers.add('Content-Length', str(content_length))
                response.headers.add('Cache-Control', 'no-cache')
                return response
            except Exception as e:
                logger.error(f"Range request error: {e}")
                # Fall back to full file
        
        # Full file request
        response = Response()
        response.headers.add('Accept-Ranges', 'bytes')
        response.headers.add('Content-Type', mime_type)
        response.headers.add('Content-Length', str(file_size))
        response.headers.add('Cache-Control', 'no-cache')
        
        def generate():
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    yield chunk
        
        return Response(generate(), status=200, mimetype=mime_type, headers={
            'Accept-Ranges': 'bytes',
            'Content-Type': mime_type,
            'Content-Length': str(file_size),
            'Cache-Control': 'no-cache'
        })