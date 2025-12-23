"""
PYQ Cloud Storage Service
Handles storing and retrieving PYQ papers from GCP Cloud Storage
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import structlog

from .gcp_service import GCPService
from ..config import get_settings

logger = structlog.get_logger(__name__)


class PYQStorageService:
    """Service for managing PYQ papers in GCP Cloud Storage"""

    def __init__(self, gcp_service: GCPService = None):
        self.settings = get_settings()
        self.gcp_service = gcp_service or GCPService(self.settings)

    def _get_paper_path(self, exam_type: str, filename: str) -> str:
        """Get the GCS path for a paper"""
        return f"pyq/{exam_type}/{filename}"

    def extract_metadata_from_filename(self, filename: str, exam_type: str) -> Dict[str, Any]:
        """Extract paper metadata from filename"""
        # Extract year
        year_match = re.search(r'20\d{2}', filename)
        year = int(year_match.group()) if year_match else datetime.now().year

        # Generate title
        name = Path(filename).stem
        title = name.replace('-', ' ').replace('_', ' ')
        title = ' '.join(word.capitalize() for word in title.split())
        title = title.replace('Ugc Net', 'UGC NET').replace('Paper Ii', 'Paper II').replace('Solved Paper', '').strip()

        # Extract subject
        filename_lower = filename.lower()
        if 'law' in filename_lower:
            subject = 'Law'
        elif 'general' in filename_lower:
            subject = 'General'
        elif 'english' in filename_lower:
            subject = 'English'
        elif 'mathematics' in filename_lower:
            subject = 'Mathematics'
        else:
            subject = 'General'

        # Add subject to title if not already present
        if subject not in title and subject != 'General':
            title = f"{title} - {subject}"

        return {
            "filename": filename,
            "title": title,
            "year": year,
            "exam_name": exam_type.replace('_', ' '),
            "subject": subject,
            "exam_type": exam_type
        }

    def upload_paper(self, exam_type: str, filename: str, json_data: List[Dict]) -> bool:
        """Upload a PYQ paper to GCS"""
        try:
            blob_path = self._get_paper_path(exam_type, filename)

            # Convert to JSON string
            json_content = json.dumps(json_data, ensure_ascii=False, indent=2)

            # Upload to GCS
            from io import BytesIO
            json_bytes = BytesIO(json_content.encode('utf-8'))

            success = self.gcp_service.upload_file(
                blob_name=blob_path,
                file_obj=json_bytes,
                content_type='application/json'
            )

            if success:
                logger.info("Uploaded PYQ paper to GCS",
                          exam_type=exam_type, filename=filename,
                          questions_count=len(json_data))

            return success

        except Exception as e:
            logger.error("Failed to upload PYQ paper",
                        exam_type=exam_type, filename=filename,
                        error=str(e), exc_info=e)
            return False

    def upload_paper_from_file(self, exam_type: str, local_file_path: str) -> bool:
        """Upload a PYQ paper from local JSON file"""
        try:
            file_path = Path(local_file_path)
            if not file_path.exists():
                logger.error("Local file not found", path=local_file_path)
                return False

            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            return self.upload_paper(exam_type, file_path.name, json_data)

        except Exception as e:
            logger.error("Failed to upload paper from file",
                        path=local_file_path, error=str(e), exc_info=e)
            return False

    def get_paper(self, exam_type: str, filename: str) -> Optional[Dict[str, Any]]:
        """Get a specific PYQ paper from GCS"""
        try:
            blob_path = self._get_paper_path(exam_type, filename)

            # Check if file exists
            if not self.gcp_service.check_file_exists(blob_path):
                logger.warning("Paper not found in GCS", exam_type=exam_type, filename=filename)
                return None

            # Open file stream and read JSON
            with self.gcp_service.open_file_stream(blob_path) as f:
                if f is None:
                    return None

                questions = json.load(f)

            # Extract metadata
            metadata = self.extract_metadata_from_filename(filename, exam_type)

            return {
                "metadata": metadata,
                "questions": questions,
                "total_questions": len(questions) if isinstance(questions, list) else 0
            }

        except Exception as e:
            logger.error("Failed to get paper from GCS",
                        exam_type=exam_type, filename=filename,
                        error=str(e), exc_info=e)
            return None

    def list_papers(self, exam_type: str = None) -> List[Dict[str, Any]]:
        """List all available papers"""
        try:
            if not self.gcp_service.client:
                logger.error("GCP client not initialized")
                return []

            bucket = self.gcp_service.client.bucket(self.gcp_service.bucket_name)

            # List blobs with pyq/ prefix
            prefix = f"pyq/{exam_type}/" if exam_type else "pyq/"
            blobs = bucket.list_blobs(prefix=prefix)

            papers = []
            for blob in blobs:
                # Skip folders/directories
                if blob.name.endswith('/'):
                    continue

                # Extract exam type and filename from path
                path_parts = blob.name.split('/')
                if len(path_parts) >= 3:  # pyq/EXAM_TYPE/filename.json
                    blob_exam_type = path_parts[1]
                    blob_filename = path_parts[2]

                    # Extract metadata
                    metadata = self.extract_metadata_from_filename(blob_filename, blob_exam_type)

                    paper_info = {
                        **metadata,
                        "gcs_path": blob.name,
                        "size": blob.size,
                        "updated": blob.updated.isoformat() if blob.updated else None,
                        "public_url": self.gcp_service.get_public_url(blob.name)
                    }

                    papers.append(paper_info)

            # Sort by year (newest first), then by title
            papers.sort(key=lambda x: (-(x.get('year', 0)), x.get('title', '')))

            logger.info("Listed PYQ papers from GCS",
                       exam_type=exam_type or "all",
                       count=len(papers))

            return papers

        except Exception as e:
            logger.error("Failed to list papers from GCS",
                        exam_type=exam_type, error=str(e), exc_info=e)
            return []

    def get_paper_summary(self) -> Dict[str, Any]:
        """Get summary statistics of all papers"""
        try:
            all_papers = self.list_papers()

            if not all_papers:
                return {
                    "total_papers": 0,
                    "available_years": [],
                    "available_exams": [],
                    "exam_counts": {},
                    "year_range": {"earliest": None, "latest": None}
                }

            # Calculate statistics
            years = [p["year"] for p in all_papers if p.get("year")]
            exams = [p["exam_name"] for p in all_papers if p.get("exam_name")]

            exam_counts = {}
            for exam in exams:
                exam_counts[exam] = exam_counts.get(exam, 0) + 1

            return {
                "total_papers": len(all_papers),
                "available_years": sorted(list(set(years)), reverse=True),
                "available_exams": sorted(list(set(exams))),
                "exam_counts": exam_counts,
                "year_range": {
                    "earliest": min(years) if years else None,
                    "latest": max(years) if years else None
                }
            }

        except Exception as e:
            logger.error("Failed to get paper summary", error=str(e), exc_info=e)
            return {"error": str(e)}

    def delete_paper(self, exam_type: str, filename: str) -> bool:
        """Delete a paper from GCS"""
        try:
            blob_path = self._get_paper_path(exam_type, filename)
            return self.gcp_service.delete_file(blob_path)

        except Exception as e:
            logger.error("Failed to delete paper",
                        exam_type=exam_type, filename=filename,
                        error=str(e), exc_info=e)
            return False