# routes/api/mpv_routes.py
import os
import urllib.parse
import mimetypes
from flask import request, jsonify, send_file, Response
from flask_login import login_required, current_user

from core.config_manager import config_manager
from core.mpv_player import MPVPlayer, MPVStreamHandler
from . import api_bp

# Initialize MPV components
mpv_player = MPVPlayer(config_manager)
mpv_stream_handler = MPVStreamHandler(config_manager)


@api_bp.route('/api/mpv/stream/<path:file_path>')
@login_required
def mpv_stream_file(file_path):
    """Stream video file with MPV-compatible range requests"""
    decoded_path = urllib.parse.unquote(file_path)
    if not os.path.exists(decoded_path):
        return "File not found", 404
    return send_file(decoded_path, conditional=True)


@api_bp.route('/api/mpv/popout')
@login_required
def mpv_popout():
    """Launch MPV popout player"""
    video_url = request.args.get('url')
    title = request.args.get('title', 'MediaFlow Player')
    
    if not video_url:
        return "No video URL provided", 400
    
    success = mpv_player.launch_mpv_popout(video_url, title)
    
    if success:
        return '''
        <html>
        <head>
            <title>MPV Player Launched</title>
            <meta http-equiv="refresh" content="2;url=/dashboard">
            <style>
                body { font-family: Arial; text-align: center; padding: 50px; background: #1a1a2e; color: white; }
                .success { color: #4caf50; font-size: 48px; }
            </style>
        </head>
        <body>
            <div class="success">✓</div>
            <h2>MPV Player Launched!</h2>
            <p>The video is playing in MPV popout window.</p>
            <p>Redirecting back to dashboard...</p>
        </body>
        </html>
        '''
    else:
        return '''
        <html>
        <head>
            <title>MPV Player Error</title>
            <style>
                body { font-family: Arial; text-align: center; padding: 50px; background: #1a1a2e; color: white; }
                .error { color: #f44336; font-size: 48px; }
            </style>
        </head>
        <body>
            <div class="error">✗</div>
            <h2>Failed to Launch MPV</h2>
            <p>Please make sure MPV is installed and in your PATH.</p>
            <p><a href="https://mpv.io/" target="_blank">Download MPV</a></p>
            <a href="/dashboard">Go back to dashboard</a>
        </body>
        </html>
        '''


@api_bp.route('/api/mpv/status')
@login_required
def mpv_status():
    """Check if MPV is available"""
    return jsonify({
        'available': mpv_player.is_available(),
        'path': mpv_player.mpv_path
    })