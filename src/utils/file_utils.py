import os
from pathlib import Path
from typing import Optional

from ..exceptions import FileProcessingError


def validate_file_exists(file_path: str) -> None:
    if not os.path.exists(file_path):
        raise FileProcessingError(f"File not found: {file_path}")


def validate_file_size(file_path: str, max_size_mb: int) -> None:
    file_size = os.path.getsize(file_path)
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        raise FileProcessingError(f"File too large: {file_size / 1024 / 1024:.1f}MB > {max_size_mb}MB")


def extract_filename(file_path: str) -> str:
    return Path(file_path).name


def extract_title(file_path: str) -> str:
    return Path(file_path).stem


def get_file_extension(file_path: str) -> str:
    return Path(file_path).suffix.lower()


def build_file_metadata(file_path: str, file_size: int, content: str) -> dict:
    return {
        "file_name": extract_filename(file_path),
        "file_size": file_size,
        "title": extract_title(file_path),
        "content_length": len(content)
    }