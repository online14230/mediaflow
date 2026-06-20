# core/collections.py

from core.database import db
from datetime import datetime
import json

class MediaCollection(db.Model):
    __tablename__ = 'media_collections'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    cover_path = db.Column(db.String(500))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    
    media_items = db.Column(db.Text, default='[]')
    
    def get_media_items(self):
        return json.loads(self.media_items) if self.media_items else []
    
    def set_media_items(self, items):
        self.media_items = json.dumps(items)
    
    def add_media(self, media_id: int, media_type: str):
        items = self.get_media_items()
        new_item = {'id': media_id, 'type': media_type}
        if new_item not in items:
            items.append(new_item)
            self.set_media_items(items)
            db.session.commit()
    
    def remove_media(self, media_id: int):
        items = self.get_media_items()
        items = [item for item in items if item.get('id') != media_id]
        self.set_media_items(items)
        db.session.commit()

class CollectionManager:
    """Manage media collections"""
    
    def __init__(self):
        pass
    
    def create_collection(self, name: str, user_id: int, description: str = None) -> MediaCollection:
        collection = MediaCollection(
            name=name,
            description=description,
            user_id=user_id
        )
        db.session.add(collection)
        db.session.commit()
        return collection
    
    def get_user_collections(self, user_id: int):
        return MediaCollection.query.filter_by(user_id=user_id).all()
    
    def get_public_collections(self):
        return MediaCollection.query.filter_by(is_public=True).all()
    
    def add_to_collection(self, collection_id: int, media_id: int, media_type: str):
        collection = MediaCollection.query.get(collection_id)
        if collection:
            collection.add_media(media_id, media_type)
            return True
        return False
    
    def remove_from_collection(self, collection_id: int, media_id: int):
        collection = MediaCollection.query.get(collection_id)
        if collection:
            collection.remove_media(media_id)
            return True
        return False