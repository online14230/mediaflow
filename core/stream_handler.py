# core/stream_handler.py

import os
import subprocess
import logging
from pathlib import Path
from flask import Response, request, send_file

logger = logging.getLogger(__name__)

class StreamHandler:
    """Handle video streaming with support for MKV files"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.chunk_size = 1024 * 1024  # 1MB chunks
        
    def get_video_mime_type(self, file_path: str) -> str:
        """Get correct MIME type for video file"""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.m4v': 'video/x-m4v',
            '.mkv': 'video/x-matroska',
            '.webm': 'video/webm',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.wmv': 'video/x-ms-wmv',
            '.flv': 'video/x-flv'
        }
        return mime_types.get(ext, 'video/mp4')
    
    def stream_video(self, file_path: str):
        """Stream video file with range request support"""
        if not os.path.exists(file_path):
            return "File not found", 404
        
        file_size = os.path.getsize(file_path)
        mime_type = self.get_video_mime_type(file_path)
        
        # Get range header for seeking support
        range_header = request.headers.get('Range', None)
        
        if range_header:
            # Parse the range header
            byte_range = range_header.strip().split('=')[1]
            start, end = byte_range.split('-')
            start = int(start)
            end = int(end) if end else file_size - 1
            content_length = end - start + 1
            
            # Read the requested range
            with open(file_path, 'rb') as f:
                f.seek(start)
                data = f.read(content_length)
            
            response = Response(data, status=206, mimetype=mime_type)
            response.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
            response.headers.add('Accept-Ranges', 'bytes')
            response.headers.add('Content-Length', str(content_length))
            return response
        
        # Full file request
        return send_file(file_path, mimetype=mime_type, conditional=True)
    
    def transcode_mkv_to_mp4(self, input_path: str, output_path: str = None) -> str:
        """Transcode MKV to MP4 using ffmpeg for better browser compatibility"""
        if not output_path:
            output_path = str(Path(input_path).with_suffix('.mp4'))
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not available, returning original file")
            return input_path
        
        # Only transcode if output doesn't exist or is older than input
        if os.path.exists(output_path):
            input_mtime = os.path.getmtime(input_path)
            output_mtime = os.path.getmtime(output_path)
            if output_mtime > input_mtime:
                return output_path
        
        # Transcode MKV to MP4 (copy video stream, convert audio if needed)
        cmd = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'copy',  # Copy video stream (no re-encoding)
            '-c:a', 'aac',   # Convert audio to AAC
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Transcoded: {input_path} -> {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Transcoding failed: {e}")
            return input_path