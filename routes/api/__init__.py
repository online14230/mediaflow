# routes/api/__init__.py
from flask import Blueprint

# Create the main blueprint
api_bp = Blueprint('api', __name__)

# Import all route modules
from .core_routes import *
from .torrent_routes import *
from .tmdb_routes import *
from .nfo_routes import *
from .metadata_routes import *
from .mpv_routes import *
from .library_routes import *
from .missing_routes import *
from .cleanup_routes import *