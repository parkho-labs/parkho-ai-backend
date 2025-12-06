"""
Custom exceptions for YouTube parser error handling.

These exceptions are used to implement the waterfall fallback chain:
1. AudioDownloadError → triggers Gemini fallback
2. TranscriptionError → triggers Gemini fallback
3. GeminiFallbackError → final error (no more fallbacks)
"""


class AudioDownloadError(Exception):
    """
    Raised when YouTube audio download fails.

    This triggers a fallback to Gemini direct video URL processing.

    Common causes:
    - Network failures (timeout, connection reset)
    - Video unavailable (deleted, private, region-locked)
    - yt-dlp extraction failures
    - Disk space errors
    """
    pass


class TranscriptionError(Exception):
    """
    Raised when audio transcription fails.

    This triggers a fallback to Gemini direct video URL processing.

    Common causes:
    - OpenAI API errors (quota exceeded, authentication failed, rate limit)
    - Audio file corruption
    - Invalid audio format
    - Transcription timeout
    - API service unavailable
    """
    pass


class GeminiFallbackError(Exception):
    """
    Raised when Gemini fallback processing fails.

    This is the final error - no more fallbacks available.

    Common causes:
    - Gemini API errors (quota exceeded, authentication failed)
    - Video not supported by Gemini
    - Response parsing failures
    - Network errors
    - Timeout
    """
    pass


class TranscriptNotAvailableError(Exception):
    """
    Raised when YouTube native transcript is not available.

    This triggers a fallback to Gemini direct video URL processing.

    Common causes:
    - Video has no captions or subtitles
    - Captions disabled by uploader
    - yt-dlp extraction failures
    - Subtitle format parsing errors
    - Language not available
    """
    pass
