# core/database.py - Complete without duplicate models

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)


class MediaItem(db.Model):
    __tablename__ = 'media_items'
    id = db.Column(db.Integer, primary_key=True)
    media_type = db.Column(db.String(20))
    title = db.Column(db.String(500))
    year = db.Column(db.Integer)
    overview = db.Column(db.Text)
    poster_path = db.Column(db.String(500))
    backdrop_path = db.Column(db.String(500))
    external_id = db.Column(db.String(50))
    external_source = db.Column(db.String(20))
    runtime = db.Column(db.Integer)
    rating = db.Column(db.Float)
    genres = db.Column(db.Text)
    director = db.Column(db.String(200))
    path = db.Column(db.String(1000))
    file_path = db.Column(db.String(1000))
    folder_path = db.Column(db.String(1000))
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    # Additional metadata fields
    cast = db.Column(db.Text)           # JSON string of actors
    writers = db.Column(db.Text)        # JSON list of writer names
    studios = db.Column(db.Text)        # JSON list of studio names
    tagline = db.Column(db.String(500))
    country = db.Column(db.String(100))
    trailer_url = db.Column(db.String(500))
    trailers = db.Column(db.Text)       # JSON list of trailer URLs


class TVShow(db.Model):
    __tablename__ = 'tv_shows'
    
    id = db.Column(db.Integer, primary_key=True)
    media_id = db.Column(db.Integer, db.ForeignKey('media_items.id'))
    tvdb_id = db.Column(db.Integer)
    tmdb_id = db.Column(db.Integer)
    imdb_id = db.Column(db.String(20))
    season_count = db.Column(db.Integer, default=0)
    episode_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20))
    network = db.Column(db.String(100))
    first_air_date = db.Column(db.String(20))
    last_air_date = db.Column(db.String(20))


class Season(db.Model):
    __tablename__ = 'seasons'
    
    id = db.Column(db.Integer, primary_key=True)
    tv_show_id = db.Column(db.Integer, db.ForeignKey('tv_shows.id'))
    season_number = db.Column(db.Integer)
    episode_count = db.Column(db.Integer, default=0)
    poster_path = db.Column(db.String(500))
    overview = db.Column(db.Text)
    air_date = db.Column(db.String(20))


class Episode(db.Model):
    __tablename__ = 'episodes'
    
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'))
    episode_number = db.Column(db.Integer)
    title = db.Column(db.String(500))
    overview = db.Column(db.Text)
    air_date = db.Column(db.String(20))
    runtime = db.Column(db.Integer)
    still_path = db.Column(db.String(500))
    file_path = db.Column(db.String(500))
    downloaded = db.Column(db.Boolean, default=False)


class UserRequest(db.Model):
    __tablename__ = 'user_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    media_type = db.Column(db.String(20))
    title = db.Column(db.String(500))
    tmdb_id = db.Column(db.String(50))          # TMDB ID for auto-approval and metadata fetch
    status = db.Column(db.String(20), default='pending')
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    approved_date = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationship to get user info
    user = db.relationship('User', foreign_keys=[user_id], backref='requests')
    approver = db.relationship('User', foreign_keys=[approved_by])


class DownloadTask(db.Model):
    __tablename__ = 'download_tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500))
    status = db.Column(db.String(20), default='queued')
    progress = db.Column(db.Float, default=0)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)