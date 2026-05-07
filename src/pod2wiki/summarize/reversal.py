"""Detect reversal-narrative red flags in summaries.

Extracted from scripts/podcast_batch_summarize.py.
"""

from __future__ import annotations

import re
from typing import Any

# Default triggers from original config + podcast_batch_summarize.py
DEFAULT_REVERSAL_TRIGGERS = [
    "而非",
    "而不是",
    "颠覆",
    "反转",
    "实际上",
    "表面上",
    "打破共识",
    "并非",
    "rather than",
    "instead of",
    "actually",
]

NUMBER_RE = re.compile(r"\d[\d.,]*\s*(?:GW|MW|TW|B|M|K|%|亿|万|千|美元|元)?", re.IGNORECASE)
PROPER_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{2,}\b")


def _extract_anchors(text: str) -> tuple[list[str], list[str]]:
    numbers = [item.strip() for item in NUMBER_RE.findall(text) if any(ch.isdigit() for ch in item)]
    proper = []
    for item in PROPER_RE.findall(text):
        if item not in proper:
            proper.append(item)
    return numbers[:5], proper[:5]


def _find_in_original(anchor: str, original: str, ctx: int = 150) -> str | None:
    lower = original.lower()
    for variant in {anchor, anchor.replace(" ", "")}:
        idx = original.find(variant)
        if idx < 0:
            idx = lower.find(variant.lower())
        if idx >= 0:
            start = max(0, idx - ctx)
            end = min(len(original), idx + len(variant) + ctx)
            return original[start:end].replace("\n", " ")
    return None


def detect_reversal_flags(
    item: dict[str, Any],
    original_text: str,
    triggers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return warnings for bullets that use punchy reversal framing around numbers."""
    active_triggers = triggers or DEFAULT_REVERSAL_TRIGGERS
    candidates: list[tuple[str, int, str]] = []
    for i, bullet in enumerate(item.get("key_points") or item.get("core_views") or []):
        candidates.append(("key_points", i, str(bullet)))
    if item.get("one_line"):
        candidates.append(("one_line", 0, str(item["one_line"])))
    if item.get("summary"):
        candidates.append(("summary", 0, str(item["summary"])))

    flags = []
    for field, index, text in candidates:
        trigger = next((needle for needle in active_triggers if needle in text), None)
        if not trigger:
            continue
        numbers, proper = _extract_anchors(text)
        if not numbers:
            continue
        evidence = []
        for anchor in numbers + proper:
            evidence.append(
                {
                    "anchor": anchor,
                    "context": _find_in_original(anchor, original_text) or "NOT FOUND in original",
                }
            )
        flags.append(
            {
                "field": field,
                "index": index,
                "trigger": trigger,
                "text": text,
                "evidence": evidence,
                "claude_action": "Verify this framing against the raw transcript before reuse.",
            }
        )
    return flags
