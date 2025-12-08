from typing import Dict, List, Any
from ..exceptions import ValidationError


def validate_job_exists(job, job_id: int) -> None:
    if not job:
        raise ValidationError(f"Job {job_id} not found")


def validate_input_sources(input_sources: List[Dict[str, Any]]) -> None:
    if not input_sources:
        raise ValidationError("No input sources provided")

    for source in input_sources:
        if "content_type" not in source:
            raise ValidationError("Missing content_type in input source")
        if "id" not in source:
            raise ValidationError("Missing id in input source")


def validate_content_results(results: List[Any]) -> None:
    if not results:
        raise ValidationError("No content parsing results")

    success_count = sum(1 for result in results if getattr(result, 'success', False))
    if success_count == 0:
        raise ValidationError("All content parsing failed")