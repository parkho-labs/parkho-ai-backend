from typing import Optional, Dict, Any


class VideoTutorError(Exception):
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class ValidationError(VideoTutorError):
    pass


class JobNotFoundError(VideoTutorError):
    def __init__(self, job_id: int):
        super().__init__(
            message=f"Job {job_id} not found",
            error_code="JOB_NOT_FOUND",
            details={"job_id": job_id}
        )


class ProcessingError(VideoTutorError):
    pass