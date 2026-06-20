# core/user_manager.py

from core.database import db, User
from flask_login import current_user
from datetime import datetime
import secrets

class UserManager:
    """Enhanced user management"""
    
    def __init__(self):
        pass
    
    def create_user(self, username: str, password: str, email: str = None, 
                    is_admin: bool = False) -> User:
        """Create a new user"""
        if User.query.filter_by(username=username).first():
            raise ValueError(f"User {username} already exists")
        
        user = User(username=username, email=email, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user
    
    def update_user_profile(self, user_id: int, **kwargs):
        """Update user profile settings"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        allowed_fields = ['email', 'avatar']
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(user, field, value)
        
        db.session.commit()
        return user
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password"""
        user = User.query.get(user_id)
        if user and user.check_password(old_password):
            user.set_password(new_password)
            db.session.commit()
            return True
        return False
    
    def get_user_stats(self, user_id: int):
        """Get user statistics"""
        from core.watch_history import WatchHistory
        
        history = WatchHistory.query.filter_by(user_id=user_id).all()
        
        total_watched = len(history)
        completed = sum(1 for h in history if h.completed)
        total_time = sum(h.position_seconds for h in history) / 3600
        
        user = User.query.get(user_id)
        
        return {
            'total_watched': total_watched,
            'completed': completed,
            'total_time_hours': round(total_time, 1),
            'member_since': user.created_at if user else datetime.utcnow()
        }
    
    def generate_api_key(self, user_id: int) -> str:
        """Generate API key for external access"""
        api_key = secrets.token_urlsafe(32)
        return api_key