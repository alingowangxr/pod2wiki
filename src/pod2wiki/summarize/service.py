"""LLM summarisation service for pod2wiki.

Extracted from scripts/fetch_podcasts.py::summarize_item / summarize_without_llm.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pod2wiki.summarize.reversal import detect_reversal_flags

from pod2wiki.errors import LLMResponseError
from pod2wiki.models import Config, HypothesisLink, SourceItem, StructuredSummary
from pod2wiki.utils import strip_html, strip_markdown_light, extract_keywords
from pod2wiki.proxy import requests_proxy


class SummarizeService:
    """Produce structured summaries from SourceItem objects."""

    def __init__(self, config: Config):
        self.config = config
        self._llm_client = None  # lazy import to avoid circular deps

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def summarize(
        self, item: SourceItem, *, no_llm: bool = False, locale: str = "zh-CN"
    ) -> StructuredSummary:
        if no_llm:
            return self._summarize_without_llm(item)
        return await self._summarize_with_llm(item, locale)

    # ------------------------------------------------------------------ #
    # No-LLM fallback
    # ------------------------------------------------------------------ #
    def _summarize_without_llm(self, item: SourceItem) -> StructuredSummary:
        text = item.raw_text or ""
        plain = strip_html(strip_markdown_light(text))
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", plain) if p.strip()]
        first = paragraphs[0] if paragraphs else plain[:500]
        if len(first) > 700:
            first = first[:700].rsplit(" ", 1)[0] + "..."
        keywords = extract_keywords(plain)
        hypotheses = self.config.hypotheses or {}
        h_links = []
        lower = plain.lower()
        for hid, hdata in hypotheses.items():
            for keyword in hdata.get("keywords", []):
                if str(keyword).lower() in lower:
                    h_links.append(
                        {
                            "hypothesis": hid,
                            "direction": "neutral",
                            "reason": f"matched keyword: {keyword}",
                        }
                    )
                    break

        summary = StructuredSummary(
            summary=first or "No summary generated. Review the raw text.",
            core_views=[f"Keyword: {kw}" for kw in keywords[:6]],
            confidence="low",
            h_links=[HypothesisLink(**h) for h in h_links],
        )
        # Post-process warnings
        flat = summary.model_dump()
        flat["key_points"] = summary.core_views
        flat["one_line"] = summary.summary
        extra_warnings = detect_reversal_flags(
            flat,
            text,
            triggers=self.config.reversal_triggers,
        )
        if not summary.verification_warnings:
            summary.verification_warnings = []
        summary.verification_warnings.extend(extra_warnings)  # type: ignore[arg-type]
        return summary

    # ------------------------------------------------------------------ #
    # LLM-backed summarisation
    # ------------------------------------------------------------------ #
    async def _summarize_with_llm(self, item: SourceItem, locale: str) -> StructuredSummary:
        text = item.raw_text or ""
        max_chars = self.config.max_transcript_chars
        if len(text) > max_chars:
            text = (
                text[: int(max_chars * 0.75)]
                + "\n\n[... omitted ...]\n\n"
                + text[-int(max_chars * 0.2) :]
            )

        system = "You summarize podcasts and long-form research articles for an investment knowledge base. Output strict JSON only."
        user = f"""Summarize this source for a karpathy-claude-wiki compatible source-summary page.

Language preference: {locale}

Return JSON with keys:
summary, core_views, key_data, related_tickers, related_concepts, predictions, h_links, speakers, key_quotes.

Hypotheses:
{json.dumps(self.config.hypotheses, ensure_ascii=False, indent=2)}

Metadata:
title={item.title}
channel={item.channel}
url={item.url}
date={item.date}

Source text:
---
{text}
---"""

        llm_cfg = self.config.llm
        # Lazy import to avoid early circular dependency
        from pod2wiki.llm_client import async_chat as llm_chat, extract_json

        content = await llm_chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            provider=llm_cfg.provider,
            model=llm_cfg.model,
            max_tokens=llm_cfg.max_tokens,
        )
        # Parse JSON
        try:
            data = extract_json(content)
            summary = StructuredSummary(**data)
        except Exception as exc:
            # Fallback
            summary = self._summarize_without_llm(item)
            summary.verification_warnings.append(
                {"type": "llm_failure", "message": f"LLM parsing failed: {exc}"}
            )

        # Verification warnings
        flat = summary.model_dump()
        flat["key_points"] = summary.core_views
        flat["one_line"] = summary.summary
        extra_warnings = detect_reversal_flags(
            flat,
            text,
            triggers=self.config.reversal_triggers,
        )
        if not summary.verification_warnings:
            summary.verification_warnings = []
        summary.verification_warnings.extend(extra_warnings)  # type: ignore[arg-type]
        return summary

    # ------------------------------------------------------------------ #
    # Translation (kept minimal; orchestrator wires it)
    # ------------------------------------------------------------------ #
    async def translate(
        self, text: str, target_locale: str, provider: str, model: str, max_tokens: int
    ) -> str:
        """Translate a chunk of text asynchronously."""
        from pod2wiki.llm_client import async_chat as llm_chat

        prompt = f"""Translate the following text into {target_locale}.

Rules:
- Preserve names, company names, ticker symbols, numbers, URLs, and units.
- Keep paragraph structure.
- Do not summarize. Translate the full text.

---
{text}
---"""
        return await llm_chat(
            [
                {
                    "role": "system",
                    "content": "You are a careful transcript translator. Do not add commentary.",
                },
                {"role": "user", "content": prompt},
            ],
            provider=provider,
            model=model,
            max_tokens=max_tokens,
            temperature=0.1,
        )
