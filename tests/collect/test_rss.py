#!/usr/bin/env python3
"""Test the RSS collector with a mock feed."""

import pytest
from pod2wiki.collect.rss import RSSCollector
from pod2wiki.models import Config, ChannelConfig


class TestRSSCollector:
    def test_build_feed_list(self):
        config = Config(
            channels=[
                ChannelConfig(name="Test", rss="http://example.com/feed"),
            ],
            blog_feeds=[{"name": "Blog", "url": "http://blog.com/feed"}],
        )
        collector = RSSCollector(config)
        assert len(collector.feeds) == 2
        assert collector.feeds[0]["name"] == "Test"

    def test_empty_feed_list(self):
        config = Config()
        collector = RSSCollector(config)
        assert collector.feeds == []

    def test_source_kind(self):
        config = Config()
        collector = RSSCollector(config)
        assert collector.source_kind == "rss"
