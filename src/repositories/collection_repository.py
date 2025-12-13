from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.collection import Collection, collection_files
from ..models.uploaded_file import UploadedFile

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

    def get_by_user(self, user_id: str) -> List[Collection]:
        return self.db.query(Collection).filter(Collection.user_id == user_id).all()

    def delete(self, collection_id: str) -> bool:
        collection = self.get_by_id(collection_id)
        if collection:
            self.db.delete(collection)
            self.db.commit()
            return True
        return False

    def add_file(self, collection_id: str, file_id: str) -> bool:
        collection = self.get_by_id(collection_id)
        if not collection:
            return False
            
        # Check if file exists
        file = self.db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not file:
            return False

        # Build insert statement for association table
        from sqlalchemy import insert
        stmt = insert(collection_files).values(collection_id=collection_id, file_id=file_id)
        try:
            self.db.execute(stmt)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            return False  # Likely already exists

    def remove_file(self, collection_id: str, file_id: str) -> bool:
        from sqlalchemy import delete
        stmt = delete(collection_files).where(
            (collection_files.c.collection_id == collection_id) & 
            (collection_files.c.file_id == file_id)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount > 0

    def get_files(self, collection_id: str) -> List[UploadedFile]:
        collection = self.get_by_id(collection_id)
        return collection.files if collection else []
