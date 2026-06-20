# app.py - Main entry point with torrent monitor

import os
import sys
from datetime import datetime
from pathlib import Path

script_dir = Path(__file__).parent.absolute()
os.chdir(script_dir)

data_dir = script_dir / "data"
data_dir.mkdir(parents=True, exist_ok=True)

import io
import logging
import platform
import socket

from flask import Flask
from flask_login import LoginManager

# Fix Windows console encoding - with error handling
if platform.system() == "Windows":
    try:
        if sys.stdout is not None and not getattr(sys.stdout, "closed", False):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        if sys.stderr is not None and not getattr(sys.stderr, "closed", False):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except (AttributeError, ValueError, OSError) as e:
        # Skip if stdout/stderr is already closed or can't be wrapped
        pass

log_dir = script_dir / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_dir / "mediaflow.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Import core modules
from core import (
    DownloadClient,
    DownloadTask,
    MediaItem,
    MediaRenamer,
    MetadataProvider,
    User,
    UserRequest,
    config_manager,
    db,
)
from core.collections import CollectionManager, MediaCollection
from core.episode_manager import EpisodeManager
from core.folder_manager import FolderManager
from core.folder_monitor import FolderMonitor
from core.media_mover import MediaMover
from core.media_player import MediaPlayer
from core.media_searcher import MediaSearcher
from core.metadata_fixer import MetadataFixer
from core.mpv_player import MPVPlayer, MPVStreamHandler
from core.recommendations import RecommendationEngine
from core.stream_handler import StreamHandler
from core.torrent_indexers import TorrentIndexerManager
from core.torrent_monitor import TorrentMonitor
from core.transcoder import VideoTranscoder
from core.user_manager import UserManager

# Import new modules
from core.watch_history import WatchHistory, WatchHistoryManager
from core.youtube_trailer import YouTubeTrailerFetcher

# Database setup
db_path = config_manager.get("database.path", str(data_dir / "mediaflow.db"))
if not os.path.isabs(db_path):
    db_path = str(script_dir / db_path)

db_dir = Path(db_path).parent
db_dir.mkdir(parents=True, exist_ok=True)

logger.info(f"Database path: {db_path}")

# Flask app initialization
app = Flask(__name__)
app.config["SECRET_KEY"] = config_manager.get("server.secret_key", os.urandom(24).hex())
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 5,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
    "connect_args": {"check_same_thread": False},
}

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access MediaFlow."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Initialize services and managers
def init_services():
    return {
        "metadata": MetadataProvider(config_manager.get("metadata.providers.tmdb", {})),
        "downloader": DownloadClient(config_manager.get("downloader", {})),
        "renamer": MediaRenamer(config_manager.get("naming", {})),
    }


services = init_services()

# Initialize managers
watch_manager = WatchHistoryManager()
collection_manager = CollectionManager()
recommendation_engine = RecommendationEngine()
user_manager = UserManager()
transcoder = VideoTranscoder(config_manager)
media_player = MediaPlayer(config_manager)
episode_manager = EpisodeManager(config_manager)
media_searcher = MediaSearcher(config_manager)
folder_manager = FolderManager(config_manager)
folder_monitor = FolderMonitor(config_manager)
folder_monitor.set_app(app)
media_mover = MediaMover(config_manager, episode_manager)
torrent_indexers = TorrentIndexerManager(config_manager)
stream_handler = StreamHandler(config_manager)
metadata_fixer = MetadataFixer(config_manager)
youtube_fetcher = YouTubeTrailerFetcher(config_manager)
mpv_player = MPVPlayer(config_manager)
mpv_stream_handler = MPVStreamHandler(config_manager)
torrent_monitor = TorrentMonitor(config_manager, media_mover)


# Database sync callback for folder monitor
def sync_database_with_filesystem(file_path, action):
    """Sync database when files are added/removed from disk"""
    import json
    import re

    from core.database import MediaItem, db
    from core.library_scanner import LibraryScanner
    from core.nfo_parser import NFOParser

    logger.info(f"DB Sync: {action} - {file_path}")

    if action == "add":
        scanner = LibraryScanner(config_manager)
        nfo_parser = NFOParser()

        file_lower = file_path.lower()
        movies_path = config_manager.get("paths.movies", "media/movies").lower()
        tv_path = config_manager.get("paths.tv_shows", "media/tv").lower()

        media_type = "movie" if movies_path in file_lower else "series"

        # Check if already in database by file path
        existing = MediaItem.query.filter_by(file_path=file_path).first()
        if existing:
            logger.info(f"File already in database: {file_path}")
            return

        folder_path = os.path.dirname(file_path)
        nfo_path = nfo_parser.find_nfo_file(folder_path, media_type)

        if nfo_path:
            if media_type == "movie":
                metadata = nfo_parser.parse_movie_nfo(nfo_path)
            else:
                metadata = nfo_parser.parse_tv_nfo(nfo_path)

            if metadata:
                # Check by title and year to avoid duplicates
                existing = MediaItem.query.filter_by(
                    media_type=media_type,
                    title=metadata.get("title", os.path.basename(folder_path)),
                ).first()

                if existing:
                    logger.info(
                        f"Media already exists with same title: {metadata.get('title')}"
                    )
                    return

                item = MediaItem(
                    media_type=media_type,
                    title=metadata.get("title", os.path.basename(folder_path)),
                    year=metadata.get("year"),
                    overview=metadata.get("plot", ""),
                    rating=metadata.get("rating"),
                    runtime=metadata.get("runtime"),
                    director=metadata.get("director"),
                    genres=json.dumps(metadata.get("genres", [])),
                    poster_path=metadata.get("poster_path"),
                    backdrop_path=metadata.get("fanart_path"),
                    path=folder_path,
                    file_path=file_path,
                    added_date=datetime.utcnow(),
                )
                db.session.add(item)
                db.session.commit()
                logger.info(f"Added from NFO: {metadata.get('title')}")
                return

        # Check by title and year from filename
        title = os.path.basename(folder_path)
        match = re.search(r"(.+?)\s*\((\d{4})\)", title)
        if match:
            title = match.group(1).strip()
            year = int(match.group(2))
        else:
            year = None

        existing = MediaItem.query.filter_by(media_type=media_type, title=title).first()

        if not existing:
            item = MediaItem(
                media_type=media_type,
                title=title,
                year=year,
                overview=f"Imported from: {os.path.basename(file_path)}",
                path=folder_path,
                file_path=file_path,
                added_date=datetime.utcnow(),
            )
            db.session.add(item)
            db.session.commit()
            logger.info(f"Added {media_type}: {title}")

    elif action == "remove":
        item = MediaItem.query.filter_by(file_path=file_path).first()
        if item:
            db.session.delete(item)
            db.session.commit()
            logger.info(f"Removed from database: {item.title}")


# Register callbacks
def on_new_media_file(file_path, media_type):
    logger.info(f"New media detected: {file_path} ({media_type})")
    if "download" in file_path.lower() or media_type == "download":
        result = media_mover.process_completed_download(file_path)
        if result["success"]:
            logger.info(f"Successfully moved to: {result['new_path']}")
        else:
            logger.error(f"Failed to move: {result.get('error')}")


folder_monitor.register_callback(on_new_media_file)
folder_monitor.register_db_sync(sync_database_with_filesystem)


# Helper functions for templates
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return ip
        except Exception:
            return "127.0.0.1"


def get_system_info():
    info = {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_version": platform.release(),
        "cpu_count": 0,
        "cpu_percent": 0,
        "memory_total": 0,
        "memory_used": 0,
        "memory_percent": 0,
        "drives": [],
        "local_ip": get_local_ip(),
        "uptime": "",
    }

    try:
        import psutil

        info["cpu_count"] = psutil.cpu_count()
        info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        info["memory_total"] = mem.total // (1024**3)
        info["memory_used"] = mem.used // (1024**3)
        info["memory_percent"] = mem.percent

        if platform.system() == "Windows":
            import string

            for letter in string.ascii_uppercase:
                drive_path = f"{letter}:\\"
                if os.path.exists(drive_path):
                    try:
                        usage = psutil.disk_usage(drive_path)
                        info["drives"].append(
                            {
                                "mountpoint": drive_path,
                                "total": usage.total // (1024**3),
                                "used": usage.used // (1024**3),
                                "free": usage.free // (1024**3),
                                "percent": usage.percent,
                            }
                        )
                    except:
                        pass
        else:
            for part in psutil.disk_partitions():
                if "cdrom" not in part.opts and "loop" not in part.device:
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        info["drives"].append(
                            {
                                "mountpoint": part.mountpoint,
                                "total": usage.total // (1024**3),
                                "used": usage.used // (1024**3),
                                "free": usage.free // (1024**3),
                                "percent": usage.percent,
                            }
                        )
                    except:
                        pass
        info["drives"].sort(key=lambda x: x["mountpoint"])

        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_delta = datetime.now() - boot_time
        days = uptime_delta.days
        hours = uptime_delta.seconds // 3600
        if days > 0:
            info["uptime"] = f"{days}d {hours}h"
        else:
            info["uptime"] = f"{hours}h"
    except:
        pass

    return info


def get_client_ip():
    from flask import request

    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0]
    elif request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    else:
        return request.remote_addr or "127.0.0.1"


@app.context_processor
def inject_globals():
    return {
        "system_info": get_system_info(),
        "client_ip": get_client_ip(),
        "config": config_manager,
        "now": datetime.now(),
    }


# Import all route blueprints
from routes.api import api_bp
from routes.auth import auth_bp
from routes.bulk_search import bulk_search_bp
from routes.db_maintenance import db_maintenance_bp
from routes.library import library_bp
from routes.media import media_bp
from routes.metadata_fix import metadata_fix_bp
from routes.requests import requests_bp
from routes.settings import settings_bp

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(media_bp)
app.register_blueprint(requests_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(api_bp)
app.register_blueprint(library_bp)
app.register_blueprint(metadata_fix_bp)
app.register_blueprint(bulk_search_bp)
app.register_blueprint(db_maintenance_bp)


# Error handlers
@app.errorhandler(404)
def not_found(e):
    from flask import render_template

    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(e):
    from flask import render_template

    db.session.rollback()
    logger.error(f"Internal server error: {e}")
    return render_template("500.html"), 500


def init_db():
    with app.app_context():
        logger.info("Initializing database...")
        db.create_all()

        # Add missing columns
        try:
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(media_items)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            conn.close()

            from sqlalchemy import text

            columns_to_add = {
                "path": "VARCHAR(1000)",
                "file_path": "VARCHAR(1000)",
                "folder_path": "VARCHAR(1000)",
                "poster_path": "VARCHAR(500)",
                "backdrop_path": "VARCHAR(500)",
                "external_id": "VARCHAR(50)",
                "external_source": "VARCHAR(20)",
                "runtime": "INTEGER",
                "rating": "FLOAT",
                "genres": "TEXT",
                "director": "VARCHAR(200)",
                "cast": "TEXT",
                "writers": "TEXT",
                "studios": "TEXT",
                "tagline": "VARCHAR(500)",
                "country": "VARCHAR(100)",
                "trailer_url": "VARCHAR(500)",
                "trailers": "TEXT",
            }

            for col, col_type in columns_to_add.items():
                if col not in existing_columns:
                    try:
                        db.session.execute(
                            text(f"ALTER TABLE media_items ADD COLUMN {col} {col_type}")
                        )
                        logger.info(f"Added column: {col}")
                    except Exception as e:
                        logger.info(f"Could not add {col}: {e}")

            # Add tmdb_id to user_requests if not exists
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(user_requests)")
            request_columns = [column[1] for column in cursor.fetchall()]
            conn.close()

            if "tmdb_id" not in request_columns:
                try:
                    db.session.execute(
                        text("ALTER TABLE user_requests ADD COLUMN tmdb_id VARCHAR(50)")
                    )
                    logger.info("Added tmdb_id column to user_requests")
                except Exception as e:
                    logger.info(f"Could not add tmdb_id: {e}")

            db.session.commit()
        except Exception as e:
            logger.info(f"Migration note: {e}")

        # Set default settings
        if config_manager.get("auto_create_folders") is None:
            config_manager.set("auto_create_folders", "true")
        if config_manager.get("auto_download_posters") is None:
            config_manager.set("auto_download_posters", "true")

        # Start folder monitoring
        folder_monitor.start_monitoring()

        # Start torrent monitoring
        torrent_monitor.start_monitoring()

        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@mediaflow.local", is_admin=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("\n" + "=" * 50)
            print("Admin user created!")
            print("  Username: admin")
            print("  Password: admin123")
            print("=" * 50 + "\n")
            logger.info("Admin user created")
        else:
            print("\nDatabase already initialized\n")


# Graceful shutdown handler - only register if in main thread
def setup_shutdown_handler():
    try:
        import signal

        def shutdown_handler(signum, frame):
            logger.info("Shutdown signal received, cleaning up...")
            folder_monitor.stop_monitoring()
            torrent_monitor.stop_monitoring()
            logger.info("Cleanup complete. Exiting...")
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
        logger.info("Shutdown handlers registered")
    except ValueError as e:
        logger.warning(f"Could not register signal handlers (not in main thread): {e}")


if __name__ == "__main__":
    init_db()
    setup_shutdown_handler()
    port = config_manager.get("server.port", 8123)
    debug = config_manager.get("server.debug", True)

    # For Windows, use a simpler server to avoid socket issues
    if platform.system() == "Windows":
        local_ip = get_local_ip()
        print(f"\n{'=' * 50}")
        print(f"MediaFlow Server Starting...")
        print(f"Local Access: http://localhost:{port}")
        print(f"Network Access: http://{local_ip}:{port}")
        print(f"Login: admin / admin123")
        print(f"{'=' * 50}\n")
        print("Press Ctrl+C to stop the server")
        print("-" * 50)

        # Use a simpler server configuration for Windows
        from werkzeug.serving import run_simple

        run_simple(
            "0.0.0.0",
            port,
            app,
            use_reloader=debug,
            use_debugger=debug,
            threaded=True,
            use_evalex=debug,
        )
    else:
        local_ip = get_local_ip()
        print(f"\n{'=' * 50}")
        print(f"MediaFlow Server Starting...")
        print(f"Local Access: http://localhost:{port}")
        print(f"Network Access: http://{local_ip}:{port}")
        print(f"Login: admin / admin123")
        print(f"{'=' * 50}\n")
        app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
