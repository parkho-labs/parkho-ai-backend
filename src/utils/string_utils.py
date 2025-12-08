import re
from typing import List

from ..exceptions import ValidationError


def clean_text(text: str) -> str:
    return ' '.join(text.split())


def extract_content_from_markdown(markdown_text: str) -> str:
    if not markdown_text or not markdown_text.strip():
        raise ValidationError("No text content found in PDF")
    return clean_text(markdown_text)


def parse_srt_to_text(srt_content: str) -> str:
    lines = srt_content.split('\n')
    transcript_lines = []

    for line in lines:
        line = line.strip()
        if line and not line.isdigit() and '-->' not in line:
            transcript_lines.append(line)

    return clean_text(' '.join(transcript_lines))


def count_pages_from_content(content: str) -> int:
    return max(1, content.count('-----'))


def truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."