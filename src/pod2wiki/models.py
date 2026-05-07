"""Pydantic data models for pod2wiki.

This module defines the canonical schemas for all data flowing through the
pipeline, replacing the previous dict[str, Any] approach.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


# ───────────────────────────  Source Items  ───────────────────────────


class SourceItem(BaseModel):
    """Unified item produced by all collectors."""

    id: str
    title: str = "Untitled"
    channel: str = "Unknown"
    author: str = ""
    date: str = ""  # ISO date string YYYY-MM-DD
    url: HttpUrl | str = ""  # type: ignore[var-annotated]
    audio_url: str = ""
    source_kind: Literal["rss", "youtube", "file", "unknown"] = "unknown"
    raw_text: str = ""
    duration_sec: int | None = None
    transcript_status: str = "unknown"

    # Whisper-related
    transcribed_by: str | None = None
    transcript_clip_seconds: int | None = None
    transcript_audio_path: Path | None = None

    # YouTube-specific
    video_id: str = ""
    search_query: str = ""

    # File-specific
    file_path: Path | None = None

    model_config = {"frozen": False}


class RSSItem(SourceItem):
    source_kind: Literal["rss"] = "rss"  # type: ignore[assignment]


class YouTubeItem(SourceItem):
    source_kind: Literal["youtube"] = "youtube"  # type: ignore[assignment]


class FileItem(SourceItem):
    source_kind: Literal["file"] = "file"  # type: ignore[assignment]


# ───────────────────────────  Summary / LLM Output  ───────────────────────────


class HypothesisLink(BaseModel):
    hypothesis: str = ""
    direction: str = "neutral"  # "support", "oppose", "neutral"
    reason: str = ""


class VerificationWarning(BaseModel):
    field: str = ""  # e.g. "key_points", "summary"
    index: int = 0
    trigger: str = ""  # the matched trigger word
    text: str = ""  # the flagged text
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    claude_action: str = "Verify this framing against the raw transcript before reuse."


class StructuredSummary(BaseModel):
    """Schema for the JSON that the LLM is expected to return."""

    summary: str = ""
    core_views: list[str] = Field(default_factory=list)
    key_data: list[str] = Field(default_factory=list)
    related_tickers: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    predictions: list[str] = Field(default_factory=list)
    h_links: list[HypothesisLink] = Field(default_factory=list)
    speakers: list[str] = Field(default_factory=list)
    key_quotes: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    verification_warnings: list[VerificationWarning] = Field(default_factory=list)

    # Back-compat alias
    @property
    def key_points(self) -> list[str]:
        return self.core_views

    # Back-compat setter
    @key_points.setter  # type: ignore[no-redef]
    def key_points(self, value: list[str]) -> None:  # type: ignore[no-redef]
        self.core_views = value


# ───────────────────────────  Config  ───────────────────────────


class WhisperConfig(BaseModel):
    enabled: bool = True
    model: str = "tiny"
    clip_seconds: int | None = 600
    auto_threshold: int = 1500


class LLMConfig(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    max_tokens: int = 4096
    translation_max_tokens: int = 4096
    report_max_tokens: int = 6000


class ChannelConfig(BaseModel):
    name: str = ""
    youtube: str = ""
    rss: str = ""
    keywords: list[str] = Field(default_factory=list)


class Config(BaseModel):
    """Validated configuration loaded from the YAML config file."""

    theme: str = "default"
    days_lookback: int = 7
    max_items_per_feed: int = 3
    max_videos_per_channel: int = 5
    max_transcript_chars: int = 15000
    whisper: WhisperConfig = Field(default_factory=WhisperConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    channels: list[ChannelConfig] = Field(default_factory=list)
    people_searches: list[str] = Field(default_factory=list)
    exec_searches: list[str] = Field(default_factory=list)
    youtube_urls: list[str] = Field(default_factory=list)
    blog_feeds: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses: dict[str, dict[str, Any]] = Field(default_factory=dict)
    reversal_triggers: list[str] = Field(default_factory=list)


# ───────────────────────────  Result  ───────────────────────────


class ProcessedItem(BaseModel):
    item: SourceItem
    structured: StructuredSummary
    source_pages: list[str] = Field(default_factory=list)
    translation_pages: list[str] = Field(default_factory=list)


class RunResult(BaseModel):
    ok: bool = True
    items_found: int = 0
    items_summarized: int = 0
    source_pages_count: int = 0
    source_pages_written: list[str] = Field(default_factory=list)
    raw_pages_written: list[str] = Field(default_factory=list)
    translation_pages_written: list[str] = Field(default_factory=list)
    insight_log: str | None = None
    verification_warnings: list[dict[str, Any]] = Field(default_factory=list)
