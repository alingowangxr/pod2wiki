"""Insight log generation for pod2wiki.

Extracted from scripts/fetch_podcasts.py::generate_insight_report / append_insight_log.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pod2wiki.models import Config, ProcessedItem
from pod2wiki.utils import format_bullets


class InsightLogService:
    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    def generate(processed: list[ProcessedItem]) -> str:
        blocks = ["# pod2wiki Insight Log"]
        for entry in processed:
            blocks.append(_item_block(entry))
        return "\n\n".join(blocks)

    def generate_llm(self, processed: list[ProcessedItem], days: int, no_llm: bool) -> str:
        if no_llm:
            return self.generate(processed)
        compact = []
        for entry in processed:
            item = entry.item
            structured = entry.structured
            compact.append(
                {
                    "title": item.title,
                    "channel": item.channel,
                    "date": item.date,
                    "url": item.url,
                    "summary": structured.summary,
                    "core_views": structured.core_views,
                    "key_data": structured.key_data,
                    "predictions": structured.predictions,
                    "h_links": [h.model_dump() for h in (structured.h_links or [])],
                    "verification_warnings": [
                        w.model_dump() for w in (structured.verification_warnings or [])
                    ],
                }
            )
        llm_cfg = self.config.llm
        prompt = f"""Write a Chinese professional investor insight log from these podcast/article summaries.

Structure:
# pod2wiki Insight Log
## 本次主线
## 内容逐条整理
## 假设影响
## 待核查红灯

Rules:
- Separate facts from interpretation.
- Mention verification warnings explicitly.
- Do not invent data not present in JSON.

Days: {days}
JSON:
{json.dumps(compact, ensure_ascii=False, indent=2)}
"""
        from llm_client import chat as llm_chat

        return llm_chat(
            [
                {
                    "role": "system",
                    "content": "You write concise Chinese investment research logs from structured source data.",
                },
                {"role": "user", "content": prompt},
            ],
            provider=llm_cfg.provider,
            model=llm_cfg.model,
            max_tokens=llm_cfg.report_max_tokens,
            temperature=0.2,
        )

    @staticmethod
    def append(path: Path, report: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        header = "# AI insights log\n\n---\n\n" if not path.exists() else "\n\n---\n\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{header}## {timestamp} scan\n\n{report.strip()}\n")


def _item_block(entry: ProcessedItem) -> str:
    item = entry.item
    structured = entry.structured
    views = structured.core_views
    warnings = structured.verification_warnings
    source_line = ", ".join(f"`{p}`" for p in entry.source_pages) if entry.source_pages else "None"
    translation_line = (
        ", ".join(f"`{p}`" for p in entry.translation_pages) if entry.translation_pages else "None"
    )
    return f"""### {item.title or "Untitled"}

📺 {item.channel or item.source_kind or "Unknown"} | 📅 {item.date or ""} | 🔗 {item.url or ""}

**TL;DR**: {structured.summary or ""}

**Key Points**
{format_bullets(views)}

**Source Pages**: {source_line}

**Translations**: {translation_line}

**Verification Warnings**
{format_bullets(warnings)}
""".strip()
