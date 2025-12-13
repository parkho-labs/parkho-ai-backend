from sqlalchemy import Column, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..core.database import Base

# Association Table (Many-to-Many)
collection_files = Table(
    'collection_files',
    Base.metadata,
    Column('collection_id', String, ForeignKey('collections.id'), primary_key=True),
    Column('file_id', String, ForeignKey('uploaded_files.id'), primary_key=True)
)

class Collection(Base):
    __tablename__ = "collections"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to Files
    files = relationship("UploadedFile", secondary=collection_files, backref="collections")
