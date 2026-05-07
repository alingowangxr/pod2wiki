"""Markdown rendering and file persistence for pod2wiki.

Extracted from scripts/fetch_podcasts.py::write_raw / write_source / write_translation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pod2wiki.models import SourceItem, StructuredSummary
from pod2wiki.utils import slugify, format_bullets


class FilePersistence:
    """Persist markdown files to disk."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def write_raw(self, item: SourceItem) -> Path:
        raw_dir = self.base_dir / "raw" / "podcasts"
        raw_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{item.date}-{slugify(item.channel)}-{slugify(item.title)}.md"
        path = raw_dir / filename
        body = self._render_raw(item)
        path.write_text(body, encoding="utf-8")
        return path

    def write_translation(self, item: SourceItem, translated: str, locale: str) -> Path:
        translation_dir = self.base_dir / "translations"
        translation_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{item.date}-{slugify(item.channel)}-{slugify(item.title)}-{slugify(locale, 12)}.md"
        )
        path = translation_dir / filename
        body = self._render_translation(item, translated, locale)
        path.write_text(body, encoding="utf-8")
        return path

    def write_source(
        self,
        item: SourceItem,
        summary: StructuredSummary,
        raw_ref: str,
        domain: str,
        locale: str,
    ) -> Path:
        source_dir = self.base_dir / "sources"
        source_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{item.date}-{slugify(item.channel)}-{slugify(item.title)}.md"
        path = source_dir / filename
        body = self._render_source(item, summary, raw_ref, domain, locale)
        path.write_text(body, encoding="utf-8")
        return path

    # ------------------------------------------------------------------ #
    # Renderers (pure functions; easy to unit-test)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _render_raw(item: SourceItem) -> str:
        transcribed_line = f"transcribed_by: {item.transcribed_by}\n" if item.transcribed_by else ""
        clip_line = (
            f"transcript_clip_seconds: {item.transcript_clip_seconds}\n"
            if item.transcript_clip_seconds
            else ""
        )
        return f"""---
title: {json.dumps(item.title, ensure_ascii=False)}
type: raw-transcript
source: {json.dumps(item.url or "", ensure_ascii=False)}
created: {item.date}
{transcribed_line}{clip_line}---

# {item.title}

Channel: {item.channel or ""}

URL: {item.url or ""}

Audio: {item.audio_url or ""}

## Raw Text

{item.raw_text or ""}
"""

    @staticmethod
    def _render_translation(item: SourceItem, translated: str, locale: str) -> str:
        return f"""---
title: {json.dumps(item.title, ensure_ascii=False)}
type: full-translation
source: {json.dumps(item.url or "", ensure_ascii=False)}
created: {item.date}
language: {locale}
---

# {item.title}

Source: {item.url or ""}

{translated}
"""

    @staticmethod
    def _render_source(
        item: SourceItem,
        summary: StructuredSummary,
        raw_ref: str,
        domain: str,
        locale: str,
    ) -> str:
        related = []
        for ticker in summary.related_tickers or []:
            related.append(f"[[{ticker}]]")
        for concept in summary.related_concepts or []:
            related.append(f"[[{concept}]]")

        transcribed_line = f"transcribed_by: {item.transcribed_by}\n" if item.transcribed_by else ""
        return f"""---
title: {json.dumps(item.title, ensure_ascii=False)}
type: source-summary
domain: {domain}
sources: [{json.dumps(raw_ref, ensure_ascii=False)}]
related: {related if related else "[]"}
created: {item.date}
updated: {datetime.now().date().isoformat()}
confidence: {summary.confidence or "medium"}
speakers: {summary.speakers or []}
language: {locale}
{transcribed_line}---

## TL;DR / 一句话摘要

{summary.summary or ""}

## Key Data / 关键数据

{format_bullets(summary.key_data)}

## Direct Quotes / 原始引文

{format_bullets(summary.key_quotes)}

## Implications / 启示

{format_bullets(summary.core_views)}

## Verifiable Predictions / 可验证预测

{format_bullets(summary.predictions)}

## Hypothesis Links / 假设关联

{format_bullets(summary.h_links)}

## Verification Warnings / 待核查红灯

{format_bullets(summary.verification_warnings)}
"""
