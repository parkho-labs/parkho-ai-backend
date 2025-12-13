from sqlalchemy.orm import Session
from src.models.collection import Collection, collection_files
from src.models.uploaded_file import UploadedFile
from typing import List, Optional
from sqlalchemy import insert, delete

class CollectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: str, name: str, description: str = None) -> Collection:
        collection = Collection(user_id=user_id, name=name, description=description)
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def get_by_id(self, collection_id: str) -> Optional[Collection]:
        return self.db.query(Collection).filter(Collection.id == collection_id).first()

    def get_all_by_user(self, user_id: str) -> List[Collection]:
        return self.db.query(Collection).filter(Collection.user_id == user_id).all()

    def delete(self, collection_id: str) -> bool:
        collection = self.get_by_id(collection_id)
        if collection:
            self.db.delete(collection)
            self.db.commit()
            return True
        return False

    def add_file(self, collection_id: str, file_id: str) -> bool:
        # Legacy single add, keeping for backward compatibility but recommend bulk
        return self.add_files_bulk(collection_id, [file_id]) > 0
        
    def add_files_bulk(self, collection_id: str, file_ids: List[str]) -> int:
        # 1. Check which files exist and are NOT already in the collection
        # This avoids unique constraint errors. Simple way: Try insert ignore or filtered select.
        # Postgres supports ON CONFLICT DO NOTHING.
        
        # Build list of dicts to insert
        values = [{"collection_id": collection_id, "file_id": fid} for fid in file_ids]
        
        if not values:
            return 0
            
        stmt = insert(collection_files).values(values).on_conflict_do_nothing()
        
        try:
            result = self.db.execute(stmt)
            self.db.commit()
            # rowcount might be accurate for inserted rows
            return result.rowcount
        except Exception as e:
            self.db.rollback()
            # Fallback or log?
            return 0

    def remove_file(self, collection_id: str, file_id: str) -> bool:
        return self.remove_files_bulk(collection_id, [file_id]) > 0

    def remove_files_bulk(self, collection_id: str, file_ids: List[str]) -> int:
        if not file_ids:
            return 0
            
        stmt = delete(collection_files).where(
            collection_files.c.collection_id == collection_id,
            collection_files.c.file_id.in_(file_ids)
        )
        
        try:
            result = self.db.execute(stmt)
            self.db.commit()
            return result.rowcount
        except:
            self.db.rollback()
            return 0
