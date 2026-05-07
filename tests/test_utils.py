"""Tests for utilities in utils.py."""

from datetime import datetime, timezone

from pod2wiki.utils import (
    extract_keywords,
    parse_date,
    parse_youtube_date,
    slugify,
    strip_html,
    strip_markdown_light,
)


class TestSlugify:
    def test_basic_slug(self) -> None:
        assert slugify("Hello World!!") == "hello-world"

    def test_chinese(self) -> None:
        result = slugify("AI 投資 播客")
        assert "ai" in result

    def test_max_len(self) -> None:
        assert len(slugify("a" * 200, max_len=50)) == 50

    def test_empty_fallback(self) -> None:
        assert slugify("!!!") == "untitled"


class TestStripHTML:
    def test_removes_tags(self) -> None:
        assert strip_html("<p>Hello</p>") == "Hello"

    def test_unescape(self) -> None:
        assert strip_html("Tom &amp; Jerry") == "Tom & Jerry"


class TestStripMarkdownLight:
    def test_removes_headers(self) -> None:
        assert strip_markdown_light("# Title\n\nbody") == "body"

    def test_removes_speaker_prefix(self) -> None:
        assert strip_markdown_light("Host: Hello") == "Hello"


class TestParseDate:
    def test_rfc822(self) -> None:
        dt = parse_date("Mon, 01 Jan 2024 00:00:00 GMT")
        assert dt == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_none(self) -> None:
        assert parse_date(None) is None

    def test_naive_date(self) -> None:
        dt = parse_date("Wed, 15 May 2024 12:30:00")
        assert dt is not None
        assert dt.tzinfo is not None


class TestParseYouTubeDate:
    def test_valid(self) -> None:
        dt = parse_youtube_date("20240101")
        assert dt == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_none(self) -> None:
        assert parse_youtube_date(None) is None

    def test_invalid(self) -> None:
        assert parse_youtube_date("notadate") is None


class TestExtractKeywords:
    def test_basic(self) -> None:
        text = "AI models are changing the world of AI."
        kws = extract_keywords(text, limit=3)
        assert len(kws) <= 3
        assert any("AI" in kw for kw in kws)

    def test_stops_ignored(self) -> None:
        text = "the and for with that"
        kws = extract_keywords(text)
        assert kws == []
