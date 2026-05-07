"""Base collector interface for pod2wiki."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from pod2wiki.models import Config, SourceItem


class BaseCollector(ABC):
    """All source collectors must inherit from this."""

    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    def collect(self, days: int, history: dict[str, str] | None = None) -> Sequence[SourceItem]:
        """Collect source items.

        Args:
            days: Number of days to look back.
            history: Optionally pass a seen-history dict to skip duplicates.

        Returns:
            A sequence of SourceItem objects.
        """
        ...

    @property
    @abstractmethod
    def source_kind(self) -> str:
        """Return the source kind string (e.g., 'rss', 'youtube')."""
        ...
