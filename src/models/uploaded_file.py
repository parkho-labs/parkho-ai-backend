from datetime import datetime, timedelta
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func

from ..core.database import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String, primary_key=True, index=True)  # UUID (This mirrors RAG File ID)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String, nullable=True)
    upload_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    cleanup_after = Column(DateTime(timezone=True), nullable=False)
    # Status: pending, indexing, completed, failed
    indexing_status = Column(String, default="pending", nullable=False)

    def __init__(self, id: str, filename: str, file_path: str, file_size: int, content_type: str = None, ttl_hours: int = 24, indexing_status: str = "pending"):
        self.id = id
        self.filename = filename
        self.file_path = file_path
        self.file_size = file_size
        self.content_type = content_type
        self.cleanup_after = datetime.utcnow() + timedelta(hours=ttl_hours)
        self.indexing_status = indexing_status

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.cleanup_after