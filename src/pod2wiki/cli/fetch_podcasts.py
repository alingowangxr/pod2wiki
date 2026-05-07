"""Slim CLI orchestrator for pod2wiki.

Extracted from scripts/fetch_podcasts.py::main (arguments 1:1 compatible).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from pod2wiki.collect.rss import RSSCollector
from pod2wiki.collect.youtube import YouTubeCollector
from pod2wiki.models import Config
from pod2wiki.persistence.file import FilePersistence
from pod2wiki.reporting.insight_log import InsightLogService
from pod2wiki.summarize.service import SummarizeService
from pod2wiki.transcribe.whisper import TranscriptionService


def load_config(path: Path) -> Config:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config must be a YAML object")
    return Config(**data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--env-file", help="Optional .env file to load before LLM calls.")
    parser.add_argument("--output-dir", help="Runtime output directory.")
    parser.add_argument("--days", type=int)
    parser.add_argument("--wiki-out")
    parser.add_argument("--domain", default="investing")
    parser.add_argument("--locale", default="zh-CN")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days-quick", action="store_true")
    parser.add_argument("--input-file", action="append", default=[])
    parser.add_argument("--title")
    parser.add_argument("--channel")
    parser.add_argument("--source-url")
    parser.add_argument("--date")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--max-items-per-feed", type=int)
    parser.add_argument("--mode", choices=["all", "rss", "youtube"], default="all")
    parser.add_argument(
        "--youtube-mode", choices=["channels", "search", "urls", "all"], default="all"
    )
    parser.add_argument("--youtube-url", action="append", default=[])
    parser.add_argument("--youtube-query", action="append", default=[])
    parser.add_argument("--youtube-max-results", type=int)
    parser.add_argument("--transcript-backend", choices=["auto", "api", "yt-dlp"], default="auto")
    parser.add_argument("--transcript-languages", default="en,en-US,en-GB,zh-Hans,zh")
    parser.add_argument("--transcript-sleep", type=float, default=1.5)
    parser.add_argument("--whisper-model", choices=["tiny", "base", "small", "medium", "large-v3"])
    parser.add_argument("--whisper-clip-seconds", type=int)
    parser.add_argument("--no-whisper", action="store_true")
    parser.add_argument("--whisper-threshold", type=int)
    parser.add_argument("--translate-full", action="store_true")
    parser.add_argument("--translation-locale", default="zh-CN")
    parser.add_argument("--write-insight-log", action="store_true")
    parser.add_argument("--insight-log")
    args = parser.parse_args()

    output = Path(args.output_dir) if args.output_dir else Path("output")
    config = load_config(Path(args.config))
    days = 1 if args.days_quick else (args.days or config.days_lookback)
    youtube_max_results = args.youtube_max_results or config.max_videos_per_channel
    max_items_per_feed = args.max_items_per_feed or getattr(config, "max_items_per_feed", None)

    if args.dry_run:
        payload = {
            "ok": True,
            "mode": "dry-run",
            "config": str(args.config),
            "days": days,
            "items": 0,
            "note": "dry-run validates config and does not call network, LLM, or write files",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    # Orchestration wiring
    rss_collector = RSSCollector(config)
    youtube_collector = YouTubeCollector(config)
    transcriber = TranscriptionService(
        model=args.whisper_model or config.whisper.model,
        clip_seconds=args.whisper_clip_seconds
        if args.whisper_clip_seconds is not None
        else config.whisper.clip_seconds,
        auto_threshold=args.whisper_threshold or config.whisper.auto_threshold,
        enabled=not args.no_whisper,
    )
    summarizer = SummarizeService(config)
    persistence = FilePersistence(output)
    insight_service = InsightLogService(config)

    history_path = output / "seen_history.json"
    history: dict[str, str] = {}
    if history_path.is_file():
        history = json.loads(history_path.read_text(encoding="utf-8"))

    # Collect items
    items = []
    if args.mode in ("all", "rss"):
        items.extend(rss_collector.collect(days, history, max_items_per_feed=max_items_per_feed))
    if args.mode in ("all", "youtube"):
        items.extend(
            youtube_collector.collect(
                days,
                history,
                youtube_mode=args.youtube_mode,
                max_results=youtube_max_results,
                transcript_backend=args.transcript_backend,
                transcript_languages=[
                    p.strip() for p in args.transcript_languages.split(",") if p.strip()
                ],
                transcript_sleep=args.transcript_sleep,
                explicit_urls=args.youtube_url,
                explicit_queries=args.youtube_query,
            )
        )

    if args.max_items is not None:
        items = items[: args.max_items]

    # Process
    processed = []
    for item in items:
        if not item.raw_text:
            continue
        # whisper if needed (placeholder)
        # summary
        structured = summarizer.summarize(item, no_llm=args.no_llm, locale=args.locale)
        raw_path = persistence.write_raw(item)
        raw_ref = str(raw_path.relative_to(output)).replace("\\", "/")
        source_path = persistence.write_source(item, structured, raw_ref, args.domain, args.locale)
        processed.append(
            {
                "item": item,
                "structured": structured,
                "source_pages": [str(source_path)],
                "translation_pages": [],
            }
        )
        if item.source_kind != "file":
            history[item.id] = datetime.now(timezone.utc).isoformat()

    # Save history
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    # Insight log
    insight_log_path = None
    if args.write_insight_log and processed:
        report = insight_service.generate_llm(processed, days, args.no_llm)
        target = Path(args.insight_log) if args.insight_log else output / "ai-insights-log.md"
        insight_service.append(target, report)
        insight_log_path = str(target)

    payload = {
        "ok": True,
        "items_found": len(items),
        "items_summarized": len(processed),
        "insight_log": insight_log_path,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
