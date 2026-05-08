"""Slim CLI orchestrator for pod2wiki.

Extracted from scripts/fetch_podcasts.py::main (arguments 1:1 compatible).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from pod2wiki.collect.rss import RSSCollector
from pod2wiki.collect.youtube import YouTubeCollector
from pod2wiki.models import Config, ProcessedItem, FileItem
from pod2wiki.persistence.file import FilePersistence
from pod2wiki.persistence.state import RunStateManager
from pod2wiki.reporting.insight_log import InsightLogService
from pod2wiki.summarize.service import SummarizeService
from pod2wiki.transcribe.whisper import TranscriptionService
from pod2wiki.utils import slugify

console = Console()


def load_config(path: Path) -> Config:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config must be a YAML object")
    return Config(**data)


async def run_orchestrator(args: Any) -> int:
    # If input files are provided and mode is default, switch to file mode for a clean run
    if args.input_file and args.mode == "all":
        args.mode = "file"

    output = Path(args.output_dir) if args.output_dir else Path("output")
    state_mgr = RunStateManager(output / "pod2wiki_v1.db")
    
    if args.env_file:
        from pod2wiki.utils import load_env_file
        load_env_file(Path(args.env_file))

    config = load_config(Path(args.config))
    days = 1 if args.days_quick else (args.days or config.days_lookback)
    youtube_max_results = args.youtube_max_results or config.max_videos_per_channel
    max_items_per_feed = args.max_items_per_feed or getattr(config, "max_items_per_feed", None)

    if args.dry_run:
        from pod2wiki.reporting.estimator import CostEstimator
        from rich.panel import Panel
        from rich.console import Console
        import sys
        
        # Use a separate console for stderr to keep stdout clean for JSON
        err_console = Console(stderr=True)
        
        estimator = CostEstimator(config)
        report = estimator.estimate(args)
        
        counts = report["counts"]
        risks = report["risks"]
        
        msg = f"""[bold]Estimated Workload:[/bold]
- RSS Feeds: {counts['rss_feeds']}
- YouTube Channels: {counts['youtube_channels']}
- [cyan]Max Potential Items: {counts['max_potential_items']}[/cyan]

[bold]Potential API Usage:[/bold]
- LLM Summaries: {counts['llm_summary_calls']}
- LLM Translations: {counts['llm_translation_calls']}
- [green]Total LLM Requests: {counts['total_llm_requests']}[/green]
- [yellow]Est. Whisper Transcriptions: {counts['estimated_transcriptions']}[/yellow]

[bold]Active Config:[/bold]
- Provider: {report['config_summary']['provider']}
- Model: {report['config_summary']['model']}
"""
        err_console.print(Panel(msg.strip(), title="Scan Dry-Run & Cost Estimate", expand=False))
        
        if risks:
            err_console.print("\n[bold red]Potential Risks Found:[/bold red]")
            for r in risks:
                color = "red" if r["level"] == "high" else "yellow"
                err_console.print(f"  [{color}]![/{color}] {r['message']}")

        payload = {
            "ok": True,
            "mode": "dry-run",
            "report": report,
            "note": "dry-run validates config and does not call network, LLM, or write files",
        }
        print(json.dumps(payload))
        return 0

    # Start Run
    llm_cfg = config.llm
    run_id = state_mgr.create_run(
        vars(args) if hasattr(args, "__dict__") else {},
        provider=llm_cfg.provider,
        model=llm_cfg.model
    )
    console.print(f"[bold cyan]Run ID:[/bold cyan] {run_id}")

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
    
    # 1. Recovery Paths
    retry_id = getattr(args, "retry_failed", None)
    resume_id = getattr(args, "resume", None)
    replay_id = getattr(args, "replay", None)
    
    if retry_id:
        items = state_mgr.get_failed_items(retry_id)
        console.print(f"[bold yellow]Retrying {len(items)} failed items from run {retry_id}[/bold yellow]")
    elif resume_id:
        # Note: get_all_items but we'll filter below or similar
        items = [i for i in state_mgr.get_all_items(resume_id) 
                 if not any(e["stage"] in ("written", "skipped") 
                            for e in state_mgr.get_run_events(resume_id, i.id))]
        console.print(f"[bold yellow]Resuming {len(items)} unfinished items from run {resume_id}[/bold yellow]")
    elif replay_id:
        items = state_mgr.get_all_items(replay_id)
        console.print(f"[bold blue]Replaying {len(items)} items from run {replay_id}[/bold blue]")
    else:
        # 2. Normal Path
        if args.input_file:
            for path_str in args.input_file:
                p = Path(path_str)
                if not p.is_file(): continue
                items.append(FileItem(
                    id=f"file:{p.name}", title=args.title or p.stem, channel=args.channel or "LocalFile",
                    date=args.date or datetime.now(timezone.utc).date().isoformat(),
                    url=args.source_url or str(p.absolute()), raw_text=p.read_text(encoding="utf-8"), file_path=p
                ))

        with console.status("[bold blue]Collecting sources...", spinner="dots"):
            collection_tasks = []
            if args.mode in ("all", "rss"):
                collection_tasks.append(rss_collector.collect(days, history, max_items_per_feed=max_items_per_feed))
            if args.mode in ("all", "youtube"):
                collection_tasks.append(youtube_collector.collect(
                    days, history, youtube_mode=args.youtube_mode, max_results=youtube_max_results,
                    transcript_backend=args.transcript_backend, transcript_sleep=args.transcript_sleep,
                    explicit_urls=args.youtube_url, explicit_queries=args.youtube_query
                ))
            if collection_tasks:
                results = await asyncio.gather(*collection_tasks)
                for res in results: items.extend(res)

    # 3. Apply Filters
    if getattr(args, "only", None):
        items = [i for i in items if i.id == args.only or args.only in i.title]
        console.print(f"[cyan]Filtered to {len(items)} items using --only '{args.only}'[/cyan]")

    if args.max_items is not None:
        items = items[: args.max_items]

    if not items:
        console.print("[yellow]No items to process.[/yellow]")
        state_mgr.finish_run(run_id, "completed")
        return 0

    for item in items:
        state_mgr.log_item_stage(run_id, item, "collected")

    console.print(f"[bold green]Processing {len(items)} items.[/bold green]")

    # Process
    until_stage = getattr(args, "until_stage", None)

    async def process_one(item, progress, task_id) -> ProcessedItem | None:
        try:
            if until_stage == "collected": return None

            progress.update(task_id, description=f"[cyan]Transcribing: {item.title[:40]}...")
            item = transcriber.maybe_transcribe(item, output / "transcripts")
            state_mgr.log_item_stage(run_id, item, "transcribed")
            if until_stage == "transcribed": return None
            
            if not item.raw_text:
                state_mgr.log_item_stage(run_id, item, "skipped", "No text content")
                return None

            progress.update(task_id, description=f"[cyan]Summarizing: {item.title[:40]}...")
            structured = await summarizer.summarize(item, no_llm=args.no_llm, locale=args.locale)
            state_mgr.log_item_stage(run_id, item, "summarized")
            
            # Log warnings
            for warn in structured.verification_warnings:
                w_type = warn.get("type") or warn.get("trigger") or "unknown"
                w_msg = warn.get("message") or warn.get("text") or ""
                state_mgr.log_warning(run_id, item.id, w_type, w_msg)

            if until_stage == "summarized": return None

            raw_path = persistence.write_raw(item)
            raw_ref = str(raw_path.relative_to(output)).replace("\\", "/")
            source_path = persistence.write_source(item, structured, raw_ref, args.domain, args.locale)
            
            translation_pages = []
            if args.translate_full and not args.no_llm:
                progress.update(task_id, description=f"[cyan]Translating: {item.title[:40]}...")
                translated = await summarizer.translate(
                    item.raw_text, args.translation_locale, llm_cfg.provider, llm_cfg.model, llm_cfg.translation_max_tokens
                )
                trans_path = persistence.write_translation(item, translated, args.translation_locale)
                translation_pages.append(str(trans_path))

            res = ProcessedItem(item=item, structured=structured, source_pages=[str(source_path)], translation_pages=translation_pages)
            if item.source_kind != "file":
                history[item.id] = datetime.now(timezone.utc).isoformat()
            
            state_mgr.log_item_stage(run_id, item, "written")
            progress.update(task_id, description=f"[green]Completed: {item.title[:40]}")
            progress.advance(task_id)
            return res
        except Exception as exc:
            state_mgr.log_item_stage(run_id, item, "failed", str(exc))
            progress.update(task_id, description=f"[red]Failed: {item.title[:40]} ({exc})")
            progress.advance(task_id)
            return None

    # Use a semaphore to limit LLM concurrency
    sem = asyncio.Semaphore(5)
    async def sem_process(item, progress, task_id):
        async with sem:
            return await process_one(item, progress, task_id)

    # Force safe spinner for legacy windows
    use_spinner = console.encoding.lower() == "utf-8"

    with Progress(
        SpinnerColumn() if use_spinner else TextColumn(""),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        main_task = progress.add_task("[bold]Overall Progress", total=len(items))
        processing_tasks = [sem_process(item, progress, main_task) for item in items]
        processed_results = await asyncio.gather(*processing_tasks)
        processed = [p for p in processed_results if p is not None]

    # Save history
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    # Post-processing
    from pod2wiki.processing.post import run_post_processors
    run_post_processors(processed, config, output)

    # Insight log
    insight_log_path = None
    if args.write_insight_log and processed:
        console.print("[bold blue]Generating insight log...")
        report = await insight_service.generate_llm_async(processed, days, args.no_llm)
        target = Path(args.insight_log) if args.insight_log else output / "ai-insights-log.md"
        insight_service.append(target, report)
        insight_log_path = str(target)

    # Optional Wiki Copy
    if args.wiki_out:
        import shutil
        wiki_root = Path(args.wiki_out)
        for entry in processed:
            # Copy source page
            for sp in entry.source_pages:
                src_p = Path(sp)
                dst_p = wiki_root / "sources" / src_p.name
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_p, dst_p)
            # Copy raw page
            raw_p = output / "raw" / "podcasts" / f"{entry.item.date}-{slugify(entry.item.channel)}-{slugify(entry.item.title)}.md"
            if raw_p.exists():
                dst_raw = wiki_root / "raw" / "podcasts" / raw_p.name
                dst_raw.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(raw_p, dst_raw)
            # Copy translations
            for tp in entry.translation_pages:
                src_tp = Path(tp)
                dst_tp = wiki_root / "translations" / src_tp.name
                dst_tp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_tp, dst_tp)

    # Final Summary Table
    table = Table(title="Run Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_row("Items Found", str(len(items)))
    table.add_row("Successfully Summarized", str(len(processed)))
    table.add_row("Failed/Skipped", str(len(items) - len(processed)))
    console.print(table)

    if insight_log_path:
        console.print(f"\n[bold green]Insight log written to:[/bold green] {insight_log_path}")
    if args.wiki_out:
        console.print(f"[bold green]Wiki pages synchronized to:[/bold green] {args.wiki_out}")

    state_mgr.finish_run(run_id, "completed")
    return 0


async def main() -> int:
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
    parser.add_argument("--mode", choices=["all", "rss", "youtube", "file"], default="all")
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

    return await run_orchestrator(args)


if __name__ == "__main__":
    asyncio.run(main())
