# core/transcoder.py

import subprocess
import os
import time
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class VideoTranscoder:
    """Handle video transcoding for different devices"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.transcode_dir = Path("data/transcode")
        self.transcode_dir.mkdir(parents=True, exist_ok=True)
        self.active_transcodes = {}
        
    def check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available"""
        # Check in current directory first
        if os.path.exists("ffmpeg.exe") or os.path.exists("ffmpeg"):
            return True
        
        # Check in PATH
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def get_transcode_command(self, input_path: str, output_path: str, 
                               quality: str = 'auto', width: int = None) -> list:
        """Generate ffmpeg transcode command"""
        cmd = ['ffmpeg', '-i', input_path]
        
        cmd.extend(['-c:v', 'libx264'])
        
        if quality == 'high':
            cmd.extend(['-crf', '18', '-preset', 'medium'])
        elif quality == 'medium':
            cmd.extend(['-crf', '23', '-preset', 'fast'])
        elif quality == 'low':
            cmd.extend(['-crf', '28', '-preset', 'veryfast'])
        else:
            cmd.extend(['-crf', '23', '-preset', 'fast'])
        
        if width:
            cmd.extend(['-vf', f'scale={width}:-2'])
        
        cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
        cmd.extend(['-movflags', '+faststart'])
        cmd.append(output_path)
        return cmd
    
    def transcode_video(self, input_path: str, quality: str = 'auto', 
                        width: int = None, callback=None) -> Optional[str]:
        """Transcode video for streaming"""
        if not self.check_ffmpeg():
            logger.warning("ffmpeg not available, returning original file")
            return input_path
        
        input_hash = str(hash(input_path + quality + str(width)))[:8]
        output_path = self.transcode_dir / f"transcode_{input_hash}.mp4"
        
        if output_path.exists():
            return str(output_path)
        
        cmd = self.get_transcode_command(input_path, str(output_path), quality, width)
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.active_transcodes[str(output_path)] = {
                'process': process,
                'started': time.time()
            }
            
            process.wait(timeout=300)
            
            if process.returncode == 0:
                return str(output_path)
            else:
                logger.error(f"Transcode failed")
                return input_path
                
        except subprocess.TimeoutExpired:
            logger.error("Transcode timeout")
            return input_path
        except Exception as e:
            logger.error(f"Transcode error: {e}")
            return input_path
    
    def get_active_transcodes(self) -> Dict:
        """Get active transcoding jobs"""
        for path, info in list(self.active_transcodes.items()):
            if info['process'].poll() is not None:
                del self.active_transcodes[path]
        
        return self.active_transcodes