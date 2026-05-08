"""RSS and blog feed collector for pod2wiki.

Extracted from scripts/fetch_podcasts.py::rss_items / collect_rss.
"""

from __future__ import annotations

import asyncio
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from pod2wiki.collect.base import BaseCollector
from pod2wiki.models import Config, RSSItem, SourceItem
from pod2wiki.proxy import httpx_proxy
from pod2wiki.utils import parse_date, strip_html

UA = "pod2wiki/0.1 (+https://github.com/alingowangxr/pod2wiki)"


def _eprint(message: str) -> None:
    print(message, file=sys.stderr)


class RSSCollector(BaseCollector):
    """Collect RSS / blog feeds."""

    @property
    def source_kind(self) -> str:
        return "rss"

    def __init__(self, config: Config):
        super().__init__(config)
        self.feeds = self._build_feed_list()

    # --------------------------------------------------------------------- #
    # helpers
    # --------------------------------------------------------------------- #
    def _build_feed_list(self) -> list[dict[str, Any]]:
        feeds: list[dict[str, Any]] = []
        for ch in self.config.channels:
            if ch.rss:
                feeds.append({"name": ch.name, "url": ch.rss, "author": ""})
        feeds.extend(self.config.blog_feeds)
        return feeds

    # --------------------------------------------------------------------- #
    # public API
    # --------------------------------------------------------------------- #
    async def collect(
        self,
        days: int,
        history: dict[str, str] | None = None,
        max_items_per_feed: int | None = None,
    ) -> list[SourceItem]:
        history = history or {}
        
        # Concurrently fetch all feeds
        tasks = [
            self._fetch_feed(feed, days, history, max_items=max_items_per_feed)
            for feed in self.feeds
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_items: list[SourceItem] = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                feed = self.feeds[i]
                _eprint(f"- feed skipped: {feed.get('name') or feed.get('url')} ({res})")
            else:
                all_items.extend(res)
        return all_items

    # --------------------------------------------------------------------- #
    # fetch logic
    # --------------------------------------------------------------------- #
    async def _fetch_feed(
        self,
        feed: dict[str, Any],
        days: int,
        history: dict[str, str],
        max_items: int | None = None,
    ) -> list[SourceItem]:
        url = feed.get("url") or feed.get("rss")
        if not url:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        proxy = httpx_proxy()
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=True, trust_env=False, proxy=proxy
        ) as client:
            response = await client.get(url, headers={"User-Agent": UA})
            response.raise_for_status()
            content = response.content

        root = ET.fromstring(content)

        ns = {
            "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
            "content": "http://purl.org/rss/1.0/modules/content/",
        }
        channel_title = root.findtext("./channel/title") or feed.get("name") or "Unknown"

        out: list[SourceItem] = []
        for item in root.findall("./channel/item"):
            if max_items is not None and len(out) >= max_items:
                break

            title = item.findtext("title") or "Untitled"
            published_raw = item.findtext("pubDate")
            published = parse_date(published_raw)
            if published and published < cutoff:
                continue

            link = item.findtext("link") or ""
            guid = item.findtext("guid") or link or title
            description = (
                item.findtext("content:encoded", namespaces=ns)
                or item.findtext("description")
                or item.findtext("itunes:summary", namespaces=ns)
                or ""
            )
            enclosure = item.find("enclosure")
            audio_url = enclosure.attrib.get("url") if enclosure is not None else ""

            record = RSSItem(
                id=guid,
                title=strip_html(title),
                channel=feed.get("name") or channel_title,
                author=feed.get("author") or "",
                date=(published or datetime.now(timezone.utc)).date().isoformat(),
                url=link or audio_url or url,
                audio_url=audio_url,
                raw_text=strip_html(description),
            )

            if record.id not in history:
                out.append(record)
        return out
