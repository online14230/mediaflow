# core/recommendations.py

from core.database import MediaItem
from core.watch_history import WatchHistory
from sqlalchemy import func

class RecommendationEngine:
    """Generate smart media recommendations"""
    
    def __init__(self):
        pass
    
    def get_recommendations(self, user_id: int, limit: int = 10):
        """Get personalized recommendations based on watch history"""
        watched_media = WatchHistory.query.filter_by(user_id=user_id).all()
        watched_ids = [h.media_id for h in watched_media]
        
        genres_freq = {}
        for history in watched_media:
            media = MediaItem.query.get(history.media_id)
            if media and media.genres:
                try:
                    import json
                    genres = json.loads(media.genres) if isinstance(media.genres, str) else media.genres
                    for genre in genres:
                        genres_freq[genre] = genres_freq.get(genre, 0) + 1
                except:
                    pass
        
        if genres_freq:
            top_genres = sorted(genres_freq.items(), key=lambda x: x[1], reverse=True)[:3]
            top_genre_names = [g[0] for g in top_genres]
            
            if watched_ids:
                recommendations = MediaItem.query.filter(
                    MediaItem.id.notin_(watched_ids)
                ).limit(limit * 2).all()
            else:
                recommendations = MediaItem.query.limit(limit * 2).all()
            
            scored = []
            for media in recommendations:
                if media.genres:
                    try:
                        import json
                        media_genres = json.loads(media.genres) if isinstance(media.genres, str) else media.genres
                        score = sum(1 for g in media_genres if g in top_genre_names)
                        scored.append((score, media))
                    except:
                        scored.append((0, media))
                else:
                    scored.append((0, media))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            return [media for score, media in scored[:limit]]
        
        return MediaItem.query.order_by(MediaItem.added_date.desc()).limit(limit).all()
    
    def get_popular_media(self, media_type: str = None, limit: int = 20):
        """Get popular media based on play counts"""
        try:
            query = db.session.query(
                MediaItem, 
                func.count(WatchHistory.id).label('play_count')
            ).outerjoin(
                WatchHistory, MediaItem.id == WatchHistory.media_id
            )
            
            if media_type:
                query = query.filter(MediaItem.media_type == media_type)
            
            results = query.group_by(MediaItem.id).order_by(
                func.count(WatchHistory.id).desc()
            ).limit(limit).all()
            
            return [media for media, count in results]
        except:
            return MediaItem.query.limit(limit).all()