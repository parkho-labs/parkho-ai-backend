from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.uploaded_file import UploadedFile


class FileRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_file(self, file_id: str, filename: str, file_path: str, file_size: int, 
    content_type: str = None, file_type: str = None, ttl_hours: int = 24, indexing_status: str = "INDEXING_PENDING") -> UploadedFile:

        uploaded_file = UploadedFile(
            id=file_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            content_type=content_type,
            file_type=file_type,
            ttl_hours=ttl_hours,
            indexing_status=indexing_status
        )
        self.session.add(uploaded_file)
        self.session.commit()
        self.session.refresh(uploaded_file)
        return uploaded_file

    def get(self, file_id: str) -> Optional[UploadedFile]:
        return self.session.query(UploadedFile).filter(UploadedFile.id == file_id).first()

    def get_expired_files(self) -> List[UploadedFile]:
        now = datetime.utcnow()
        return self.session.query(UploadedFile).filter(UploadedFile.cleanup_after < now).all()

    def delete_file(self, file_id: str) -> bool:
        uploaded_file = self.get(file_id)
        if uploaded_file:
            self.session.delete(uploaded_file)
            self.session.commit()
            return True
        return False

    def cleanup_expired_files(self) -> int:
        expired_files = self.get_expired_files()
        count = len(expired_files)
        for file in expired_files:
            self.session.delete(file)
        self.session.commit()
        return count