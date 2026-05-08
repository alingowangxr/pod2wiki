"""Common utilities (migrated from fetch_podcasts.py)."""

from __future__ import annotations

import email.utils
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any


# ─── text / date / slug helpers ────────────────────────────


def slugify(text: str, max_len: int = 80) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", text.strip().lower(), flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return (value or "untitled")[:max_len].strip("-")


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", unescape(text)).strip()
    return text


def strip_markdown_light(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        line = re.sub(
            r"^\s*(Host|Guest|Interviewer|Speaker|主持人|嘉宾)\s*:\s*",
            "",
            line,
            flags=re.IGNORECASE,
        )
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[*_`>]+", "", cleaned)
    return cleaned.strip()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = email.utils.parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_youtube_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_recent_youtube(value: str | None, days: int) -> bool:
    parsed = parse_youtube_date(value)
    if not parsed:
        return True
    return parsed >= datetime.now(timezone.utc) - timedelta(days=days)


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9+.-]{2,}", text)
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "have",
        "has",
        "you",
        "your",
        "host",
        "guest",
        "speaker",
        "interviewer",
        "podcast",
        "transcript",
    }
    counts: dict[str, int] = {}
    for word in words:
        key = word.strip()
        if key.lower() in stop:
            continue
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].lower()))
    return [word for word, _count in ranked[:limit]]


def format_bullets(items: list[str] | list[dict[str, Any]]) -> str:
    if not items:
        return "- None"
    lines = []
    for item in items:
        if isinstance(item, dict):
            lines.append("- " + "; ".join(f"{k}: {v}" for k, v in item.items()))
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def load_env_file(path: Path) -> None:
    """Load key-value pairs from a file into os.environ."""
    import os
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip("'").strip('"')
