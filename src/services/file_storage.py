import os
import shutil
import uuid
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from pathlib import Path

from ..repositories.file_repository import FileRepository
from ..models.uploaded_file import UploadedFile
from ..config import get_settings
from ..api.v1.schemas import StandardAPIResponse

settings = get_settings()


class FileStorageService:
    def __init__(self, file_repo: FileRepository):
        self.file_repo = file_repo
        self.storage_dir = Path(getattr(settings, 'file_storage_dir', './uploaded_files'))
        self.storage_dir.mkdir(exist_ok=True)

        self.file_limits = {
            "pdf": 10 * 1024 * 1024,   # 10MB
            "docx": 5 * 1024 * 1024,   # 5MB
            "doc": 5 * 1024 * 1024,    # 5MB
        }
        self.allowed_extensions = {".pdf", ".docx", ".doc"}

    def create_validation_error(self, message: str, error_code: str = "VALIDATION_ERROR") -> StandardAPIResponse:
        return StandardAPIResponse.error(message=message, error_code=error_code)

    def validate_file(self, file: UploadFile) -> tuple[bool, Optional[str]]:
        if not file.filename:
            return False, "No filename provided"

        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in self.allowed_extensions:
            return False, f"Unsupported file type: {file_ext}"

        file_type = file_ext[1:]
        if hasattr(file.file, 'seek') and hasattr(file.file, 'tell'):
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            max_size = self.file_limits.get(file_type)
            if max_size and file_size > max_size:
                return False, f"File too large: {file_size} bytes (max: {max_size})"

        return True, None

    async def store_file(self, file: UploadFile, ttl_hours: int = 24) -> str:
        is_valid, error_msg = self.validate_file(file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        try:
            file_id = str(uuid.uuid4())
            file_ext = os.path.splitext(file.filename)[1].lower()
            stored_filename = f"{file_id}{file_ext}"
            file_path = self.storage_dir / stored_filename

            with open(file_path, "wb") as stored_file:
                shutil.copyfileobj(file.file, stored_file)

            # Persist metadata to DB
            self.file_repo.create_file(
                file_id=file_id,
                filename=file.filename,
                file_path=str(file_path),
                file_size=file_path.stat().st_size,
                content_type=file.content_type,
                ttl_hours=ttl_hours
            )

            return file_id

        except Exception as e:
            if 'file_path' in locals() and file_path.exists():
                file_path.unlink()
            raise HTTPException(status_code=500, detail=f"Failed to store file: {str(e)}")

    def get_file_path(self, file_id: str) -> Optional[str]:
        uploaded_file = self.file_repo.get(file_id)
        if uploaded_file and os.path.exists(uploaded_file.file_path):
            return uploaded_file.file_path
        return None
        
    def get_file_metadata(self, file_id: str) -> Optional[UploadedFile]:
        return self.file_repo.get(file_id)

    def delete_file(self, file_id: str) -> bool:
        uploaded_file = self.file_repo.get(file_id)
        if not uploaded_file:
            return False

        try:
            if os.path.exists(uploaded_file.file_path):
                os.remove(uploaded_file.file_path)
            self.file_repo.delete_file(file_id)
            return True
        except Exception:
            return False

    def cleanup_expired_files(self) -> int:
        expired_files = self.file_repo.get_expired_files()
        cleaned_count = 0

        for uploaded_file in expired_files:
            try:
                if os.path.exists(uploaded_file.file_path):
                    os.remove(uploaded_file.file_path)
                cleaned_count += 1
            except Exception:
                pass

        self.file_repo.cleanup_expired_files()
        return cleaned_count