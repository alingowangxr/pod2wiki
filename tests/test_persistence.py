"""Unit tests for the markdown renderers in FilePersistence."""

from pod2wiki.models import RSSItem, StructuredSummary
from pod2wiki.persistence.file import FilePersistence


class TestRenderRaw:
    def test_render_raw_basic(self):
        item = RSSItem(id="id1", title="Hello", date="2024-01-01")
        fp = FilePersistence.__new__(FilePersistence)  # minimal instance for static method
        rendered = fp._render_raw(item)
        assert "Hello" in rendered
        assert "raw-transcript" in rendered
        assert "2024-01-01" in rendered


class TestRenderSource:
    def test_render_source_basic(self):
        item = RSSItem(id="id1", title="Hello", date="2024-01-01", url="http://example.com")
        summary = StructuredSummary(summary="tl;dr", core_views=["view1"])
        fp = FilePersistence.__new__(FilePersistence)
        rendered = fp._render_source(item, summary, "raw/podcasts/ref.md", "investing", "zh-CN")
        assert "tl;dr" in rendered
        assert "investing" in rendered
        assert "source-summary" in rendered

    def test_render_source_with_transcribed(self):
        item = RSSItem(id="id1", title="Hello", date="2024-01-01", transcribed_by="whisper-tiny")
        summary = StructuredSummary()
        fp = FilePersistence.__new__(FilePersistence)
        rendered = fp._render_source(item, summary, "ref", "investing", "zh-CN")
        assert "transcribed_by: whisper-tiny" in rendered
