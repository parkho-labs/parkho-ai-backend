from datetime import datetime
import uuid
from sqlalchemy import Column, Integer, String, DateTime, Date
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import sqlalchemy as sa

from ..core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, index=True, default=generate_uuid)
    firebase_uid = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)