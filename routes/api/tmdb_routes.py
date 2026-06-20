# routes/api/tmdb_routes.py
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from core import MediaItem, db
from core.config_manager import config_manager
from flask import jsonify, request
from flask_login import current_user, login_required

from . import api_bp
from .core_routes import get_services

logger = logging.getLogger(__name__)


@api_bp.route("/api/tmdb/search")
@login_required
def tmdb_search():
    """Search TMDB for movies or TV series"""
    query = request.args.get("query", "")
    media_type = request.args.get("type", "movie")

    if not query:
        return jsonify({"results": []})

    services = get_services()

    if media_type == "movie":
        results = services["metadata"].search_movies(query)
    else:
        results = services["metadata"].search_tv_series(query)

    return jsonify({"results": results})


@api_bp.route("/api/tmdb/details")
@login_required
def tmdb_details():
    """Get detailed metadata from TMDB/TVDB"""
    media_type = request.args.get("type", "movie")
    external_id = request.args.get("id")

    if not external_id:
        return jsonify({"success": False, "error": "No ID provided"})

    services = get_services()

    if media_type == "movie":
        details = services["metadata"].get_movie_details(external_id)
    else:
        details = services["metadata"].get_series_details(external_id)

    if details:
        return jsonify({"success": True, "details": details})
    else:
        return jsonify({"success": False, "error": "Failed to fetch details"})


@api_bp.route("/api/torrents/search-media", methods=["POST"])
@login_required
def search_media_torrents():
    """Search for torrents for a movie or TV series (for TMDB add flow)"""
    data = request.json
    media_type = data.get("type")
    title = data.get("title")
    year = data.get("year")

    services = get_services()

    if media_type == "movie":
        results = services["torrent_indexers"].search_movie(title, year, "1080p")
    else:
        results = services["torrent_indexers"].search_series(title, year)

    return jsonify({"results": results})


@api_bp.route("/api/downloaders/list")
@login_required
def list_downloaders():
    """List available download clients"""
    downloaders = []

    # Check qBittorrent
    qb_config = {
        "host": config_manager.get("downloader.host", "http://localhost:8080"),
        "username": config_manager.get("downloader.username", "admin"),
        "password": config_manager.get("downloader.password", "adminadmin"),
    }

    qb_available = False
    try:
        import requests

        response = requests.get(qb_config["host"], timeout=5)
        qb_available = response.status_code < 500
    except:
        qb_available = False

    downloaders.append(
        {
            "type": "qbittorrent",
            "name": "qBittorrent",
            "host": qb_config["host"],
            "available": qb_available,
        }
    )

    # Check Transmission
    transmission_config = {
        "host": config_manager.get("transmission.host", "http://localhost:9091"),
        "username": config_manager.get("transmission.username", ""),
        "password": config_manager.get("transmission.password", ""),
    }

    transmission_available = False
    if transmission_config["host"]:
        try:
            import requests

            response = requests.get(transmission_config["host"], timeout=5)
            transmission_available = response.status_code < 500
        except:
            transmission_available = False

    downloaders.append(
        {
            "type": "transmission",
            "name": "Transmission",
            "host": transmission_config["host"],
            "available": transmission_available,
        }
    )

    return jsonify({"downloaders": downloaders})


@api_bp.route("/api/tmdb/add-with-torrent", methods=["POST"])
@login_required
def tmdb_add_with_torrent():
    """Add media from TMDB/TVDB to library with selected torrent and downloader"""
    import requests
    from core.download_client import DownloadClient
    from core.folder_manager import FolderManager
    from core.nfo_parser import NFOParser
    from core.transmission_client import TransmissionClient

    from .core_routes import get_services

    data = request.json
    media_type = data.get("type")
    external_id = data.get("external_id")
    downloader_type = data.get("downloader", "qbittorrent")
    magnet = data.get("magnet")

    if not magnet:
        return jsonify({"success": False, "error": "No magnet link provided"})

    folder_manager = FolderManager(config_manager)
    services = get_services()

    if media_type == "movie":
        metadata = services["metadata"].get_movie_details(external_id)
        if metadata:
            folder_path = None
            if config_manager.get("auto_create_folders", "true") == "true":
                folder_path = folder_manager.create_movie_folder(
                    metadata["title"], metadata.get("year")
                )
                logger.info(f"Created folder for movie: {folder_path}")

                if (
                    folder_path
                    and config_manager.get("auto_download_posters", "true") == "true"
                ):
                    if metadata.get("poster_path"):
                        poster_url = (
                            f"https://image.tmdb.org/t/p/w500{metadata['poster_path']}"
                        )
                        saved_poster = folder_manager.save_poster(
                            folder_path, poster_url
                        )
                        if saved_poster:
                            metadata["poster_path"] = saved_poster

                    if metadata.get("backdrop_path"):
                        backdrop_url = f"https://image.tmdb.org/t/p/w1280{metadata['backdrop_path']}"
                        saved_backdrop = folder_manager.save_backdrop(
                            folder_path, backdrop_url
                        )
                        if saved_backdrop:
                            metadata["backdrop_path"] = saved_backdrop

            existing = MediaItem.query.filter_by(
                media_type="movie", title=metadata["title"], year=metadata.get("year")
            ).first()

            if existing:
                return jsonify({"success": False, "error": "Movie already in library"})

            item = MediaItem(
                media_type="movie",
                title=metadata["title"],
                year=metadata.get("year"),
                overview=metadata.get("overview", ""),
                poster_path=metadata.get("poster_path"),
                backdrop_path=metadata.get("backdrop_path"),
                rating=metadata.get("rating"),
                runtime=metadata.get("runtime"),
                director=metadata.get("director"),
                genres=json.dumps(metadata.get("genres", [])),
                cast=json.dumps(metadata.get("cast", [])),
                path=folder_path if folder_path else "",
                external_id=str(external_id),
                external_source="tmdb",
                added_date=datetime.utcnow(),
            )
            db.session.add(item)
            db.session.commit()

            if folder_path:
                nfo_parser = NFOParser()
                nfo_path = os.path.join(folder_path, "movie.nfo")
                nfo_parser.write_movie_nfo(nfo_path, metadata)
                logger.info(f"Created NFO file: {nfo_path}")

            download_triggered = False
            try:
                save_path = config_manager.get("paths.downloads", "downloads")

                if downloader_type == "transmission":
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
                        "password": config_manager.get(
                            "downloader.password", "adminadmin"
                        ),
                    }
                    downloader = DownloadClient(download_config)
                    success = downloader.add_torrent(magnet, save_path, None)

                if success:
                    download_triggered = True
                    logger.info(
                        f"Torrent added to {downloader_type} for: {metadata['title']}"
                    )
            except Exception as e:
                logger.error(f"Failed to add torrent: {e}")

            message = f"Added {metadata['title']} to library"
            if download_triggered:
                message += f" and torrent sent to {downloader_type}"
            else:
                message += ". Failed to add torrent to download client"

            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "download_triggered": download_triggered,
                }
            )

    elif media_type == "tv" or media_type == "series":
        metadata = services["metadata"].get_series_details(external_id)
        if metadata:
            folder_path = None
            if config_manager.get("auto_create_folders", "true") == "true":
                folder_path = folder_manager.create_series_folder(
                    metadata["title"], metadata.get("year")
                )
                logger.info(f"Created folder for series: {folder_path}")

                if (
                    folder_path
                    and config_manager.get("auto_download_posters", "true") == "true"
                ):
                    if metadata.get("poster_path"):
                        poster_url = (
                            f"https://image.tmdb.org/t/p/w500{metadata['poster_path']}"
                        )
                        saved_poster = folder_manager.save_poster(
                            folder_path, poster_url
                        )
                        if saved_poster:
                            metadata["poster_path"] = saved_poster

                    if metadata.get("backdrop_path"):
                        backdrop_url = f"https://image.tmdb.org/t/p/w1280{metadata['backdrop_path']}"
                        saved_backdrop = folder_manager.save_backdrop(
                            folder_path, backdrop_url
                        )
                        if saved_backdrop:
                            metadata["backdrop_path"] = saved_backdrop

            existing = MediaItem.query.filter_by(
                media_type="series", title=metadata["title"], year=metadata.get("year")
            ).first()

            if existing:
                return jsonify({"success": False, "error": "Series already in library"})

            item = MediaItem(
                media_type="series",
                title=metadata["title"],
                year=metadata.get("year"),
                overview=metadata.get("overview", ""),
                poster_path=metadata.get("poster_path"),
                backdrop_path=metadata.get("backdrop_path"),
                rating=metadata.get("rating"),
                genres=json.dumps(metadata.get("genres", [])),
                cast=json.dumps(metadata.get("cast", [])),
                path=folder_path if folder_path else "",
                external_id=str(external_id),
                external_source="tmdb",
                added_date=datetime.utcnow(),
            )
            db.session.add(item)
            db.session.commit()

            if folder_path:
                nfo_parser = NFOParser()
                nfo_path = os.path.join(folder_path, "tvshow.nfo")
                try:
                    import xml.etree.ElementTree as ET

                    root = ET.Element("tvshow")
                    ET.SubElement(root, "title").text = metadata["title"]
                    if metadata.get("year"):
                        ET.SubElement(root, "year").text = str(metadata["year"])
                    ET.SubElement(root, "plot").text = metadata.get("overview", "")
                    if metadata.get("rating"):
                        ET.SubElement(root, "rating").text = str(metadata["rating"])
                    if metadata.get("poster_path"):
                        art_elem = ET.SubElement(root, "art")
                        ET.SubElement(art_elem, "poster").text = metadata["poster_path"]
                    tree = ET.ElementTree(root)
                    tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
                    logger.info(f"Created TV NFO file: {nfo_path}")
                except Exception as e:
                    logger.error(f"Failed to create TV NFO: {e}")

            download_triggered = False
            try:
                save_path = config_manager.get("paths.downloads", "downloads")

                series_results = services["torrent_indexers"].search_series(
                    metadata["title"], metadata.get("year")
                )
                if series_results:
                    series_magnet = series_results[0].get("magnet") or series_results[
                        0
                    ].get("download_url")
                    if series_magnet:
                        if downloader_type == "transmission":
                            transmission_config = {
                                "host": config_manager.get(
                                    "transmission.host", "http://localhost:9091"
                                ),
                                "username": config_manager.get(
                                    "transmission.username", ""
                                ),
                                "password": config_manager.get(
                                    "transmission.password", ""
                                ),
                            }
                            downloader = TransmissionClient(transmission_config)
                            success = downloader.add_torrent(
                                series_magnet, save_path, paused=False
                            )
                        else:
                            download_config = {
                                "host": config_manager.get(
                                    "downloader.host", "http://localhost:8080"
                                ),
                                "username": config_manager.get(
                                    "downloader.username", "admin"
                                ),
                                "password": config_manager.get(
                                    "downloader.password", "adminadmin"
                                ),
                            }
                            downloader = DownloadClient(download_config)
                            success = downloader.add_torrent(
                                series_magnet, save_path, None
                            )

                        if success:
                            download_triggered = True
                            logger.info(
                                f"Series torrent added to {downloader_type} for: {metadata['title']}"
                            )
            except Exception as e:
                logger.error(f"Failed to add series torrent: {e}")

            message = f"Added {metadata['title']} to library"
            if download_triggered:
                message += f" and torrent sent to {downloader_type}"
            else:
                message += ". Failed to add torrent to download client"

            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "download_triggered": download_triggered,
                }
            )

    return jsonify({"success": False, "error": "Failed to add media"})


@api_bp.route("/api/tmdb/new-releases")
@login_required
def tmdb_new_releases():
    """Get new releases from TMDB"""
    media_type = request.args.get("type", "movie")

    api_key = config_manager.get("metadata.providers.tmdb.api_key", "")

    if not api_key:
        return jsonify({"results": [], "error": "TMDB API key not configured"})

    try:
        import requests

        if media_type == "movie":
            url = "https://api.themoviedb.org/3/movie/upcoming"
        else:
            url = "https://api.themoviedb.org/3/tv/on_the_air"

        response = requests.get(
            url, params={"api_key": api_key, "language": "en-US"}, timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return jsonify({"results": data.get("results", [])[:20]})
        else:
            return jsonify({"results": []})
    except Exception as e:
        logger.error(f"Failed to fetch new releases: {e}")
        return jsonify({"results": []})


@api_bp.route("/api/tmdb/status")
@login_required
def tmdb_status():
    """Check if TMDB API key is configured"""
    api_key = config_manager.get("metadata.providers.tmdb.api_key", "")
    has_key = api_key is not None and api_key != ""

    return jsonify(
        {
            "has_key": has_key,
            "message": "API key configured"
            if has_key
            else "No API key found. Please add in Settings.",
        }
    )


@api_bp.route("/api/movie/add-torrent", methods=["POST"])
@login_required
def movie_add_torrent():
    """Add torrent for an existing movie"""
    from core.config_manager import config_manager
    from core.download_client import DownloadClient
    from core.transmission_client import TransmissionClient

    data = request.json
    movie_id = data.get("movie_id")
    downloader_type = data.get("downloader", "qbittorrent")
    magnet = data.get("magnet")

    logger.info(
        f"Adding movie torrent - Movie ID: {movie_id}, Downloader: {downloader_type}"
    )
    logger.info(f"Magnet link (first 100 chars): {magnet[:100] if magnet else 'None'}")

    if not magnet:
        return jsonify({"success": False, "error": "No magnet link provided"})

    movie = MediaItem.query.get(movie_id)
    if not movie:
        return jsonify({"success": False, "error": "Movie not found"})

    download_triggered = False
    try:
        save_path = config_manager.get("paths.downloads", "downloads")

        if downloader_type == "transmission":
            transmission_config = {
                "host": config_manager.get(
                    "transmission.host", "http://localhost:9091"
                ),
                "username": config_manager.get("transmission.username", ""),
                "password": config_manager.get("transmission.password", ""),
            }
            logger.info(
                f"Using Transmission with config: {transmission_config['host']}"
            )
            downloader = TransmissionClient(transmission_config)
            success = downloader.add_torrent(magnet, save_path, paused=False)
        else:
            download_config = {
                "host": config_manager.get("downloader.host", "http://localhost:8080"),
                "username": config_manager.get("downloader.username", "admin"),
                "password": config_manager.get("downloader.password", "adminadmin"),
            }
            logger.info(f"Using qBittorrent with config: {download_config['host']}")
            downloader = DownloadClient(download_config)
            success = downloader.add_torrent(magnet, save_path, None)

        if success:
            download_triggered = True
            logger.info(
                f"Torrent added to {downloader_type} for existing movie: {movie.title}"
            )

            if movie.path and os.path.exists(movie.path):
                marker_file = os.path.join(movie.path, ".download_started")
                with open(marker_file, "w") as f:
                    f.write(
                        f"Download started at {datetime.now()}\nMagnet: {magnet}\nClient: {downloader_type}"
                    )
                logger.info(f"Created marker file: {marker_file}")
    except Exception as e:
        logger.error(f"Failed to add torrent: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

    if download_triggered:
        message = f'Torrent sent to {downloader_type} for "{movie.title}"'
        return jsonify(
            {"success": True, "message": message, "download_triggered": True}
        )
    else:
        return jsonify(
            {"success": False, "error": "Failed to add torrent to download client"}
        )


@api_bp.route("/api/series/add-torrent", methods=["POST"])
@login_required
def series_add_torrent():
    """Add torrent for an existing series"""
    from core.config_manager import config_manager
    from core.download_client import DownloadClient
    from core.transmission_client import TransmissionClient

    data = request.json
    series_id = data.get("series_id")
    downloader_type = data.get("downloader", "qbittorrent")
    magnet = data.get("magnet")

    logger.info(
        f"Adding series torrent - Series ID: {series_id}, Downloader: {downloader_type}"
    )
    logger.info(f"Magnet link (first 100 chars): {magnet[:100] if magnet else 'None'}")

    if not magnet:
        return jsonify({"success": False, "error": "No magnet link provided"})

    series = MediaItem.query.get(series_id)
    if not series:
        return jsonify({"success": False, "error": "Series not found"})

    download_triggered = False
    try:
        save_path = config_manager.get("paths.downloads", "downloads")

        series_title_clean = (
            series.title.replace("/", "_").replace("\\", "_").replace(":", "_")
        )
        series_folder_name = (
            f"{series_title_clean} ({series.year})"
            if series.year
            else series_title_clean
        )
        series_folder = os.path.join(
            config_manager.get("paths.tv_shows", "media/tv"), series_folder_name
        )
        os.makedirs(series_folder, exist_ok=True)
        logger.info(f"Created series folder: {series_folder}")

        if downloader_type == "transmission":
            transmission_config = {
                "host": config_manager.get(
                    "transmission.host", "http://localhost:9091"
                ),
                "username": config_manager.get("transmission.username", ""),
                "password": config_manager.get("transmission.password", ""),
            }
            logger.info(
                f"Using Transmission with config: {transmission_config['host']}"
            )
            downloader = TransmissionClient(transmission_config)
            success = downloader.add_torrent(magnet, series_folder, paused=False)
        else:
            download_config = {
                "host": config_manager.get("downloader.host", "http://localhost:8080"),
                "username": config_manager.get("downloader.username", "admin"),
                "password": config_manager.get("downloader.password", "adminadmin"),
            }
            logger.info(f"Using qBittorrent with config: {download_config['host']}")
            downloader = DownloadClient(download_config)
            success = downloader.add_torrent(magnet, series_folder, None)

        if success:
            download_triggered = True
            logger.info(
                f"Torrent added to {downloader_type} for existing series: {series.title}"
            )

            if series.path and os.path.exists(series.path):
                marker_file = os.path.join(series_folder, ".download_started")
                with open(marker_file, "w") as f:
                    f.write(
                        f"Download started at {datetime.now()}\nMagnet: {magnet}\nClient: {downloader_type}"
                    )
                logger.info(f"Created marker file: {marker_file}")
    except Exception as e:
        logger.error(f"Failed to add torrent: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

    if download_triggered:
        message = f'Torrent sent to {downloader_type} for "{series.title}"'
        return jsonify(
            {"success": True, "message": message, "download_triggered": True}
        )
    else:
        return jsonify(
            {"success": False, "error": "Failed to add torrent to download client"}
        )


@api_bp.route("/api/series/search-episode-torrents", methods=["POST"])
@login_required
def search_episode_torrents():
    """Search for torrents for a specific episode"""
    from .core_routes import get_services

    data = request.json
    series_id = data.get("series_id")
    season = data.get("season")
    episode = data.get("episode")

    logger.info(
        f"Searching episode torrents - Series ID: {series_id}, Season: {season}, Episode: {episode}"
    )

    series = MediaItem.query.get(series_id)
    if not series:
        return jsonify({"success": False, "error": "Series not found"})

    services = get_services()
    results = services["torrent_indexers"].search_episode(
        series.title, season, episode, "1080p"
    )

    logger.info(
        f"Found {len(results)} torrent results for {series.title} S{season:02d}E{episode:02d}"
    )

    return jsonify({"results": results})


@api_bp.route("/api/series/add-episode-torrent", methods=["POST"])
@login_required
def series_add_episode_torrent():
    """Add torrent for a specific episode of an existing series"""
    from core.config_manager import config_manager
    from core.download_client import DownloadClient
    from core.transmission_client import TransmissionClient

    data = request.json
    series_id = data.get("series_id")
    season = data.get("season")
    episode = data.get("episode")
    downloader_type = data.get("downloader", "qbittorrent")
    magnet = data.get("magnet")

    logger.info(
        f"Adding episode torrent - Series ID: {series_id}, Season: {season}, Episode: {episode}, Downloader: {downloader_type}"
    )
    logger.info(f"Magnet link (first 100 chars): {magnet[:100] if magnet else 'None'}")

    if not magnet:
        return jsonify({"success": False, "error": "No magnet link provided"})

    series = MediaItem.query.get(series_id)
    if not series:
        return jsonify({"success": False, "error": "Series not found"})

    download_triggered = False
    error_message = None
    try:
        save_path = config_manager.get("paths.downloads", "downloads")

        series_title_clean = (
            series.title.replace("/", "_").replace("\\", "_").replace(":", "_")
        )
        series_folder_name = (
            f"{series_title_clean} ({series.year})"
            if series.year
            else series_title_clean
        )
        series_folder = os.path.join(
            config_manager.get("paths.tv_shows", "media/tv"), series_folder_name
        )
        season_folder = os.path.join(series_folder, f"Season {season:02d}")

        os.makedirs(season_folder, exist_ok=True)
        logger.info(f"Created season folder: {season_folder}")

        if downloader_type == "transmission":
            transmission_config = {
                "host": config_manager.get(
                    "transmission.host", "http://localhost:9091"
                ),
                "username": config_manager.get("transmission.username", ""),
                "password": config_manager.get("transmission.password", ""),
            }
            logger.info(
                f"Using Transmission with config: {transmission_config['host']}"
            )
            downloader = TransmissionClient(transmission_config)
            success = downloader.add_torrent(magnet, season_folder, paused=False)
            if success:
                download_triggered = True
                logger.info(f"Successfully added to Transmission")
            else:
                error_message = "Transmission add failed"
        else:
            download_config = {
                "host": config_manager.get("downloader.host", "http://localhost:8080"),
                "username": config_manager.get("downloader.username", "admin"),
                "password": config_manager.get("downloader.password", "adminadmin"),
            }
            logger.info(f"Using qBittorrent with config: {download_config['host']}")
            downloader = DownloadClient(download_config)
            success = downloader.add_torrent(magnet, season_folder, None)
            if success:
                download_triggered = True
                logger.info(f"Successfully added to qBittorrent")
            else:
                error_message = "qBittorrent add failed"

        if success:
            marker_file = os.path.join(
                season_folder, f".download_started_S{season:02d}E{episode:02d}"
            )
            with open(marker_file, "w") as f:
                f.write(
                    f"Download started at {datetime.now()}\nMagnet: {magnet}\nClient: {downloader_type}\nSeason: {season}\nEpisode: {episode}"
                )
            logger.info(f"Created marker file: {marker_file}")
    except Exception as e:
        logger.error(f"Failed to add episode torrent: {e}")
        import traceback

        traceback.print_exc()
        error_message = str(e)

    if download_triggered:
        message = f'Episode S{season:02d}E{episode:02d} of "{series.title}" sent to {downloader_type}'
        return jsonify(
            {"success": True, "message": message, "download_triggered": True}
        )
    else:
        return jsonify(
            {
                "success": False,
                "error": error_message or "Failed to add torrent to download client",
            }
        )


# ==================== MANUAL LINKING ENDPOINTS ====================


@api_bp.route("/api/series/scan-local-files/<int:series_id>")
@login_required
def scan_local_files(series_id):
    """Scan series folder for video files"""
    series = MediaItem.query.get_or_404(series_id)

    if not series.path or not os.path.exists(series.path):
        return jsonify({"files": []})

    video_extensions = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm"}
    video_files = []

    for root, dirs, files in os.walk(series.path):
        for file in files:
            if Path(file).suffix.lower() in video_extensions:
                video_files.append(os.path.join(root, file))

    return jsonify({"files": video_files})


@api_bp.route("/api/series/list-files/<int:series_id>")
@login_required
def list_series_files(series_id):
    """List files in series folder for manual linking"""
    series = MediaItem.query.get_or_404(series_id)
    file_type = request.args.get("type", "video")

    if not series.path or not os.path.exists(series.path):
        return jsonify({"files": []})

    if file_type == "image":
        extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    else:
        extensions = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm"}

    files = []
    for root, dirs, files_in_dir in os.walk(series.path):
        for file in files_in_dir:
            if Path(file).suffix.lower() in extensions:
                files.append(os.path.join(root, file))

    return jsonify({"files": files})


@api_bp.route("/api/series/<int:series_id>/seasons")
@login_required
def get_series_seasons(series_id):
    """Get available seasons and episodes for a series"""
    from core.database import Episode, Season, TVShow

    series = MediaItem.query.get_or_404(series_id)
    tv_show = TVShow.query.filter_by(media_id=series_id).first()

    seasons = {}
    if tv_show:
        season_records = Season.query.filter_by(tv_show_id=tv_show.id).all()
        for season in season_records:
            episodes = Episode.query.filter_by(season_id=season.id).all()
            seasons[season.season_number] = {
                "episodes": [ep.episode_number for ep in episodes]
            }

    return jsonify({"seasons": seasons})


@api_bp.route("/api/series/link-file-to-episode", methods=["POST"])
@login_required
def link_file_to_episode():
    """Manually link a file to an episode"""
    import os

    from core.database import Episode, Season, TVShow

    data = request.json
    series_id = data.get("series_id")
    season_num = data.get("season")
    episode_num = data.get("episode")
    file_path = data.get("file_path")

    logger.info(
        f"Linking file to episode - Series: {series_id}, Season: {season_num}, Episode: {episode_num}"
    )
    logger.info(f"File path: {file_path}")

    file_path = file_path.replace("\\", "/")
    file_path = re.sub(r"/+", "/", file_path)

    series = MediaItem.query.get_or_404(series_id)

    tv_show = TVShow.query.filter_by(media_id=series_id).first()
    if not tv_show:
        tv_show = TVShow(media_id=series_id)
        db.session.add(tv_show)
        db.session.commit()
        logger.info(f"Created TVShow record for series {series_id}")

    season = Season.query.filter_by(
        tv_show_id=tv_show.id, season_number=season_num
    ).first()
    if not season:
        season = Season(tv_show_id=tv_show.id, season_number=season_num)
        db.session.add(season)
        db.session.commit()
        logger.info(f"Created Season {season_num} for series {series_id}")

    episode = Episode.query.filter_by(
        season_id=season.id, episode_number=episode_num
    ).first()
    if not episode:
        episode = Episode(
            season_id=season.id,
            episode_number=episode_num,
            title=f"Episode {episode_num}",
            file_path=file_path,
            downloaded=True,
        )
        db.session.add(episode)
        logger.info(f"Created new Episode {episode_num} for Season {season_num}")
    else:
        episode.file_path = file_path
        episode.downloaded = True
        logger.info(f"Updated existing Episode {episode_num} for Season {season_num}")

    db.session.commit()

    verify_episode = Episode.query.filter_by(
        season_id=season.id, episode_number=episode_num
    ).first()
    if verify_episode:
        logger.info(
            f"Verified episode saved: ID {verify_episode.id}, Path: {verify_episode.file_path}"
        )
    else:
        logger.error("Episode verification failed!")

    return jsonify(
        {
            "success": True,
            "message": f"Episode S{season_num:02d}E{episode_num:02d} linked",
        }
    )


@api_bp.route("/api/series/batch-link-files", methods=["POST"])
@login_required
def batch_link_files():
    """Batch link multiple files to episodes"""
    from core.database import Episode, Season, TVShow

    data = request.json
    series_id = data.get("series_id")
    links = data.get("links", [])

    series = MediaItem.query.get_or_404(series_id)

    tv_show = TVShow.query.filter_by(media_id=series_id).first()
    if not tv_show:
        tv_show = TVShow(media_id=series_id)
        db.session.add(tv_show)
        db.session.commit()

    linked_count = 0

    for link in links:
        season_num = link.get("season")
        episode_num = link.get("episode")
        file_path = link.get("file_path")

        if not season_num or not episode_num or not file_path:
            continue

        file_path = file_path.replace("\\", "/")
        file_path = re.sub(r"/+", "/", file_path)

        season = Season.query.filter_by(
            tv_show_id=tv_show.id, season_number=season_num
        ).first()
        if not season:
            season = Season(tv_show_id=tv_show.id, season_number=season_num)
            db.session.add(season)
            db.session.commit()

        episode = Episode.query.filter_by(
            season_id=season.id, episode_number=episode_num
        ).first()
        if not episode:
            episode = Episode(
                season_id=season.id,
                episode_number=episode_num,
                title=f"Episode {episode_num}",
                file_path=file_path,
                downloaded=True,
            )
            db.session.add(episode)
            linked_count += 1
        elif not episode.file_path:
            episode.file_path = file_path
            episode.downloaded = True
            linked_count += 1

        db.session.commit()

    return jsonify({"success": True, "linked": linked_count})


@api_bp.route("/api/series/auto-link-episodes/<int:series_id>", methods=["POST"])
@login_required
def auto_link_episodes(series_id):
    """Automatically link episodes based on filename patterns"""
    import re

    from core.database import Episode, Season, TVShow

    series = MediaItem.query.get_or_404(series_id)

    if not series.path or not os.path.exists(series.path):
        return jsonify({"linked": 0})

    tv_show = TVShow.query.filter_by(media_id=series_id).first()
    if not tv_show:
        tv_show = TVShow(media_id=series_id)
        db.session.add(tv_show)
        db.session.commit()

    video_extensions = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm"}
    linked_count = 0

    for root, dirs, files in os.walk(series.path):
        for file in files:
            if Path(file).suffix.lower() in video_extensions:
                file_path = os.path.join(root, file)

                patterns = [
                    r"[Ss](\d{1,2})[Ee](\d{1,3})",
                    r"(\d{1,2})x(\d{1,3})",
                ]

                for pattern in patterns:
                    match = re.search(pattern, file, re.IGNORECASE)
                    if match:
                        season_num = int(match.group(1))
                        episode_num = int(match.group(2))

                        season = Season.query.filter_by(
                            tv_show_id=tv_show.id, season_number=season_num
                        ).first()
                        if not season:
                            season = Season(
                                tv_show_id=tv_show.id, season_number=season_num
                            )
                            db.session.add(season)
                            db.session.commit()

                        episode = Episode.query.filter_by(
                            season_id=season.id, episode_number=episode_num
                        ).first()
                        if not episode:
                            episode = Episode(
                                season_id=season.id,
                                episode_number=episode_num,
                                title=f"Episode {episode_num}",
                                file_path=file_path,
                                downloaded=True,
                            )
                            db.session.add(episode)
                            linked_count += 1
                        elif not episode.file_path:
                            episode.file_path = file_path
                            episode.downloaded = True
                            linked_count += 1

                        db.session.commit()
                        break

    return jsonify({"linked": linked_count})


@api_bp.route("/api/series/link-poster", methods=["POST"])
@login_required
def link_series_poster():
    """Manually link a poster file to a series"""
    data = request.json
    series_id = data.get("series_id")
    file_path = data.get("file_path")

    file_path = file_path.replace("\\", "/")
    file_path = re.sub(r"/+", "/", file_path)

    series = MediaItem.query.get_or_404(series_id)
    series.poster_path = file_path
    db.session.commit()

    logger.info(f"Poster linked for series {series.title}: {file_path}")

    return jsonify({"success": True, "message": "Poster updated", "path": file_path})


@api_bp.route("/api/series/link-backdrop", methods=["POST"])
@login_required
def link_series_backdrop():
    """Manually link a backdrop file to a series"""
    data = request.json
    series_id = data.get("series_id")
    file_path = data.get("file_path")

    file_path = file_path.replace("\\", "/")
    file_path = re.sub(r"/+", "/", file_path)

    series = MediaItem.query.get_or_404(series_id)
    series.backdrop_path = file_path
    db.session.commit()

    logger.info(f"Backdrop linked for series {series.title}: {file_path}")

    return jsonify({"success": True, "message": "Backdrop updated", "path": file_path})


@api_bp.route("/api/series/clear-poster/<int:series_id>", methods=["POST"])
@login_required
def clear_series_poster(series_id):
    """Clear the poster for a series"""
    series = MediaItem.query.get_or_404(series_id)
    series.poster_path = None
    db.session.commit()
    return jsonify({"success": True})


@api_bp.route("/api/series/clear-backdrop/<int:series_id>", methods=["POST"])
@login_required
def clear_series_backdrop(series_id):
    """Clear the backdrop for a series"""
    series = MediaItem.query.get_or_404(series_id)
    series.backdrop_path = None
    db.session.commit()
    return jsonify({"success": True})


@api_bp.route("/api/series/apply-metadata", methods=["POST"])
@login_required
def apply_series_metadata():
    """Apply metadata from TMDB to a series"""
    import json

    from core.metadata_provider import MetadataProvider

    data = request.json
    series_id = data.get("series_id")
    tmdb_id = data.get("tmdb_id")

    series = MediaItem.query.get_or_404(series_id)

    tmdb_config = config_manager.get("metadata.providers.tmdb", {})
    tmdb_provider = MetadataProvider(tmdb_config)

    details = tmdb_provider.get_series_details(tmdb_id)

    if not details:
        return jsonify(
            {"success": False, "error": "Failed to fetch metadata from TMDB"}
        )

    if details.get("title"):
        series.title = details["title"]
    if details.get("year"):
        series.year = int(details["year"]) if details["year"].isdigit() else series.year
    if details.get("overview"):
        series.overview = details["overview"]
    if details.get("poster_path"):
        series.poster_path = details["poster_path"]
    if details.get("backdrop_path"):
        series.backdrop_path = details["backdrop_path"]
    if details.get("rating"):
        series.rating = details["rating"]
    if details.get("genres"):
        series.genres = json.dumps(details["genres"])
    if details.get("cast"):
        series.cast = json.dumps(details["cast"])

    series.external_id = str(tmdb_id)
    series.external_source = "tmdb"

    db.session.commit()

    return jsonify({"success": True, "message": "Metadata applied successfully"})


# ==================== PATH CORRECTION ENDPOINTS ====================


@api_bp.route("/api/series/find-folders/<int:series_id>")
@login_required
def find_series_folders(series_id):
    """Find all folders in TV path that might contain this series"""
    series = MediaItem.query.get_or_404(series_id)
    tv_path = config_manager.get("paths.tv_shows", "media/tv")

    folders = []
    if os.path.exists(tv_path):
        for folder in os.listdir(tv_path):
            folder_path = os.path.join(tv_path, folder)
            if os.path.isdir(folder_path):
                video_count = 0
                video_extensions = {
                    ".mkv",
                    ".mp4",
                    ".avi",
                    ".mov",
                    ".wmv",
                    ".m4v",
                    ".webm",
                }
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        if Path(file).suffix.lower() in video_extensions:
                            video_count += 1

                folders.append(
                    {"name": folder, "path": folder_path, "episode_count": video_count}
                )

    return jsonify({"folders": folders})


@api_bp.route("/api/series/check-path", methods=["POST"])
@login_required
def check_path_exists():
    """Check if a path exists on the filesystem"""
    data = request.json
    path = data.get("path", "")

    path = path.replace("\\", "/")

    exists = os.path.exists(path)
    is_dir = os.path.isdir(path) if exists else False

    return jsonify({"exists": exists, "is_dir": is_dir, "path": path})


@api_bp.route("/api/series/update-path", methods=["POST"])
@login_required
def update_series_path():
    """Update the path for a series"""
    data = request.json
    series_id = data.get("series_id")
    new_path = data.get("path")

    new_path = new_path.replace("\\", "/")
    new_path = re.sub(r"/+", "/", new_path)
    new_path = new_path.rstrip("/")

    series = MediaItem.query.get_or_404(series_id)
    series.path = new_path
    db.session.commit()

    return jsonify({"success": True, "message": "Path updated", "path": new_path})


# ==================== FILE BROWSER ENDPOINT ====================


@api_bp.route("/api/browser/list-directory", methods=["POST"])
@login_required
def list_directory():
    """List files and directories for manual file browsing"""
    from pathlib import Path

    data = request.json
    path = data.get("path", "/")

    path = path.replace("\\", "/")

    if not os.path.exists(path):
        return jsonify({"error": "Path does not exist", "files": []})

    if not os.path.isdir(path):
        return jsonify({"error": "Path is not a directory", "files": []})

    files = []
    video_extensions = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm"}

    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            is_dir = os.path.isdir(item_path)
            is_video = not is_dir and Path(item).suffix.lower() in video_extensions

            size_str = ""
            if not is_dir:
                try:
                    size = os.path.getsize(item_path)
                    if size > 1024 * 1024 * 1024:
                        size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"
                    elif size > 1024 * 1024:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    elif size > 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size} B"
                except:
                    pass

            files.append(
                {
                    "name": item,
                    "path": item_path.replace("\\", "/"),
                    "is_dir": is_dir,
                    "is_video": is_video,
                    "size_str": size_str,
                }
            )
    except PermissionError:
        return jsonify({"error": "Permission denied", "files": []})

    return jsonify({"files": files})


# ==================== MOVIE MANUAL LINKING ENDPOINTS ====================


@api_bp.route("/api/movie/list-files/<int:movie_id>")
@login_required
def list_movie_files(movie_id):
    """List video files in movie folder for manual linking"""
    movie = MediaItem.query.get_or_404(movie_id)

    if not movie.path or not os.path.exists(movie.path):
        return jsonify({"files": []})

    video_extensions = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm"}
    files = []

    # Check if movie.path is a file or directory
    if os.path.isfile(movie.path):
        # Single file
        if Path(movie.path).suffix.lower() in video_extensions:
            files.append(movie.path)
    else:
        # Directory - scan for video files
        for root, dirs, files_in_dir in os.walk(movie.path):
            for file in files_in_dir:
                if Path(file).suffix.lower() in video_extensions:
                    files.append(os.path.join(root, file))

    return jsonify({"files": files})


@api_bp.route("/api/movie/link-file", methods=["POST"])
@login_required
def link_movie_file():
    """Manually link a file to a movie"""
    data = request.json
    movie_id = data.get("movie_id")
    file_path = data.get("file_path")

    logger.info(f"Linking file to movie - Movie ID: {movie_id}")
    logger.info(f"File path: {file_path}")

    file_path = file_path.replace("\\", "/")
    file_path = re.sub(r"/+", "/", file_path)

    movie = MediaItem.query.get_or_404(movie_id)
    movie.file_path = file_path
    movie.path = os.path.dirname(file_path) if os.path.isfile(file_path) else file_path

    db.session.commit()

    logger.info(f"Movie file linked: {movie.title} -> {file_path}")

    return jsonify({"success": True, "message": f"File linked to {movie.title}"})
