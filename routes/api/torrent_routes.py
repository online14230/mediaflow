# routes/api/torrent_routes.py
import logging

from core.config_manager import config_manager
from core.download_client import DownloadClient
from flask import jsonify, request
from flask_login import login_required

from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route("/api/torrent/add-manual", methods=["POST"])
@login_required
def add_manual_torrent():
    """Manually add a magnet link to a download client"""
    from core.config_manager import config_manager
    from core.database import MediaItem
    from core.download_client import DownloadClient
    from core.transmission_client import TransmissionClient

    data = request.json
    magnet = data.get("magnet")
    client = data.get("client", "qbittorrent")
    series_id = data.get("series_id")
    movie_id = data.get("movie_id")

    if not magnet:
        return jsonify({"success": False, "error": "No magnet link provided"})

    download_triggered = False
    try:
        save_path = config_manager.get("paths.downloads", "downloads")

        # If series_id is provided, try to use the series folder
        if series_id:
            series = MediaItem.query.get(series_id)
            if series and series.path:
                save_path = series.path
        # If movie_id is provided, try to use the movie folder
        elif movie_id:
            movie = MediaItem.query.get(movie_id)
            if movie and movie.path:
                if os.path.isfile(movie.path):
                    save_path = os.path.dirname(movie.path)
                else:
                    save_path = movie.path

        if client == "transmission":
            transmission_config = {
                "host": config_manager.get(
                    "transmission.host", "http://localhost:9091"
                ),
                "username": config_manager.get("transmission.username", ""),
                "password": config_manager.get("transmission.password", ""),
            }
            downloader = TransmissionClient(transmission_config)
            success = downloader.add_torrent(magnet, save_path, paused=False)
        else:
            download_config = {
                "host": config_manager.get("downloader.host", "http://localhost:8080"),
                "username": config_manager.get("downloader.username", "admin"),
                "password": config_manager.get("downloader.password", "adminadmin"),
            }
            downloader = DownloadClient(download_config)
            success = downloader.add_torrent(magnet, save_path, None)

        if success:
            download_triggered = True
            logger.info(f"Manual magnet added to {client}: {magnet[:100]}...")
    except Exception as e:
        logger.error(f"Failed to add manual magnet: {e}")
        return jsonify({"success": False, "error": str(e)})

    if download_triggered:
        return jsonify({"success": True, "message": f"Magnet added to {client}"})
    else:
        return jsonify({"success": False, "error": "Failed to add to download client"})


@api_bp.route("/api/search/torrents", methods=["POST"])
@login_required
def search_torrents():
    from .core_routes import get_services

    data = request.json
    services = get_services()
    media_type = data.get("type")
    title = data.get("title")
    year = data.get("year")
    season = data.get("season")
    episode = data.get("episode")
    quality = data.get("quality", "1080p")

    if media_type == "movie":
        results = services["torrent_indexers"].search_movie(title, year, quality)
    else:
        results = services["torrent_indexers"].search_episode(
            title, season, episode, quality
        )

    return jsonify({"results": results})

    @api_bp.route("/api/torrent/add-manual", methods=["POST"])  # pyright: ignore[reportUnreachable]
    @login_required
    def add_manual_torrent():
        """Manually add a magnet link to a download client"""
        from core.config_manager import config_manager
        from core.database import MediaItem
        from core.download_client import DownloadClient
        from core.transmission_client import TransmissionClient

        data = request.json
        magnet = data.get("magnet")
        client = data.get("client", "qbittorrent")
        series_id = data.get("series_id")

        if not magnet:
            return jsonify({"success": False, "error": "No magnet link provided"})

        download_triggered = False
        try:
            save_path = config_manager.get("paths.downloads", "downloads")

            # If series_id is provided, try to use the series folder
            if series_id:
                series = MediaItem.query.get(series_id)
                if series and series.path:
                    save_path = series.path

            if client == "transmission":
                transmission_config = {
                    "host": config_manager.get(
                        "transmission.host", "http://localhost:9091"
                    ),
                    "username": config_manager.get("transmission.username", ""),
                    "password": config_manager.get("transmission.password", ""),
                }
                downloader = TransmissionClient(transmission_config)
                success = downloader.add_torrent(magnet, save_path, paused=False)
            else:
                download_config = {
                    "host": config_manager.get(
                        "downloader.host", "http://localhost:8080"
                    ),
                    "username": config_manager.get("downloader.username", "admin"),
                    "password": config_manager.get("downloader.password", "adminadmin"),
                }
                downloader = DownloadClient(download_config)
                success = downloader.add_torrent(magnet, save_path, None)

            if success:
                download_triggered = True
                logger.info(f"Manual magnet added to {client}: {magnet[:100]}...")
        except Exception as e:
            logger.error(f"Failed to add manual magnet: {e}")
            return jsonify({"success": False, "error": str(e)})

        if download_triggered:
            return jsonify({"success": True, "message": f"Magnet added to {client}"})
        else:
            return jsonify(
                {"success": False, "error": "Failed to add to download client"}
            )


def add_torrent():
    try:
        data = request.json
        magnet = data.get("magnet")
        save_path = data.get("save_path")
        category = data.get("category", "mediaflow")

        if not magnet:
            return jsonify({"success": False, "error": "No magnet link provided"})

        download_config = {
            "host": config_manager.get("downloader.host", "http://localhost:8080"),
            "username": config_manager.get("downloader.username", "admin"),
            "password": config_manager.get("downloader.password", "adminadmin"),
        }
        downloader = DownloadClient(download_config)

        success = downloader.add_torrent(magnet, save_path, category)

        if success:
            return jsonify(
                {"success": True, "message": "Torrent added to download queue"}
            )
        else:
            return jsonify({"success": False, "error": "Failed to add torrent"})
    except Exception as e:
        logger.error(f"Error adding torrent: {e}")
        return jsonify({"success": False, "error": str(e)})


@api_bp.route("/api/torrent/select-and-add", methods=["POST"])
@login_required
def select_and_add_torrent():
    try:
        data = request.json
        magnet = data.get("magnet")
        media_type = data.get("media_type")
        title = data.get("title")
        season = data.get("season")
        episode = data.get("episode")

        if not magnet:
            return jsonify({"success": False, "error": "No magnet link provided"})

        if not magnet.startswith("magnet:?"):
            return jsonify({"success": False, "error": "Invalid magnet link format"})

        if "xt=urn:btih:" not in magnet:
            return jsonify(
                {"success": False, "error": "Invalid magnet link: missing torrent hash"}
            )

        logger.info(f"Adding torrent: {title} - S{season}E{episode}")
        logger.info(f"Magnet link (truncated): {magnet[:150]}...")

        if media_type == "movie":
            save_path = config_manager.get("paths.downloads", "downloads")
            category = None
        else:
            save_path = config_manager.get("paths.downloads", "downloads")
            category = None

        download_config = {
            "host": config_manager.get("downloader.host", "http://localhost:8080"),
            "username": config_manager.get("downloader.username", "admin"),
            "password": config_manager.get("downloader.password", "adminadmin"),
        }

        downloader = DownloadClient(download_config)
        success = downloader.add_torrent(magnet, save_path, category)

        if success:
            logger.info("Successfully added torrent to qBittorrent")
            return jsonify(
                {"success": True, "message": "Torrent added to download queue"}
            )
        else:
            logger.error("Failed to add torrent to qBittorrent")
            return jsonify(
                {
                    "success": False,
                    "error": "Failed to add to qBittorrent. Check that qBittorrent is running and the magnet link is valid.",
                }
            )

    except Exception as e:
        logger.error(f"Add torrent error: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})
