"""Base error types for pod2wiki."""


class Pod2WikiError(Exception):
    """Base exception for all pod2wiki errors."""

    pass


class FeedFetchError(Pod2WikiError):
    """RSS/Feed fetching failed."""

    pass


class TranscriptUnavailableError(Pod2WikiError):
    """Transcript/subtitle could not be retrieved."""

    pass


class LLMResponseError(Pod2WikiError):
    """LLM API returned an unexpected or invalid response."""

    pass


class AudioTranscriptionError(Pod2WikiError):
    """Whisper/faster-whisper transcription failed."""

    pass


class ValidationError(Pod2WikiError):
    """Data validation failed (e.g. missing required field)."""

    pass


class ConfigError(Pod2WikiError):
    """Configuration error (missing file, invalid YAML, etc.)."""

    pass
