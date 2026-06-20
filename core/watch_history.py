# core/watch_history.py

from datetime import datetime
from core.database import db

class WatchHistory(db.Model):
    __tablename__ = 'watch_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    media_id = db.Column(db.Integer, db.ForeignKey('media_items.id'))
    media_type = db.Column(db.String(20))
    progress = db.Column(db.Float, default=0)
    position_seconds = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    last_played = db.Column(db.DateTime, default=datetime.utcnow)
    play_count = db.Column(db.Integer, default=1)
    
    def __repr__(self):
        return f'<WatchHistory {self.user_id}:{self.media_id}>'

class WatchHistoryManager:
    """Track user watch history and progress"""
    
    def __init__(self):
        pass
    
    def update_progress(self, user_id: int, media_id: int, media_type: str, 
                        position_seconds: int, duration_seconds: int):
        """Update watch progress for a media item"""
        progress = (position_seconds / duration_seconds * 100) if duration_seconds > 0 else 0
        
        history = WatchHistory.query.filter_by(
            user_id=user_id, 
            media_id=media_id,
            media_type=media_type
        ).first()
        
        if history:
            history.progress = progress
            history.position_seconds = position_seconds
            history.last_played = datetime.utcnow()
            history.play_count += 1
            history.completed = progress >= 95
        else:
            history = WatchHistory(
                user_id=user_id,
                media_id=media_id,
                media_type=media_type,
                progress=progress,
                position_seconds=position_seconds,
                completed=progress >= 95,
                play_count=1
            )
            db.session.add(history)
        
        db.session.commit()
        return history
    
    def get_continue_watching(self, user_id: int, limit: int = 10):
        """Get items the user has started but not finished"""
        return WatchHistory.query.filter_by(
            user_id=user_id,
            completed=False
        ).filter(
            WatchHistory.progress > 0
        ).order_by(
            WatchHistory.last_played.desc()
        ).limit(limit).all()
    
    def get_recently_watched(self, user_id: int, limit: int = 20):
        """Get recently watched items"""
        return WatchHistory.query.filter_by(
            user_id=user_id
        ).order_by(
            WatchHistory.last_played.desc()
        ).limit(limit).all()
    
    def get_resume_position(self, user_id: int, media_id: int) -> int:
        """Get resume position for a media item"""
        history = WatchHistory.query.filter_by(
            user_id=user_id,
            media_id=media_id
        ).first()
        
        if history and not history.completed:
            return history.position_seconds
        return 0
    
    def mark_completed(self, user_id: int, media_id: int, media_type: str):
        """Mark media as fully watched"""
        history = WatchHistory.query.filter_by(
            user_id=user_id,
            media_id=media_id,
            media_type=media_type
        ).first()
        
        if history:
            history.completed = True
            history.progress = 100
            db.session.commit()