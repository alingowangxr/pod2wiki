"""Unified CLI for pod2wiki using Typer and Rich."""

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from pod2wiki.models import Config
from pod2wiki.llm_client import resolve_provider

app = typer.Typer(help="pod2wiki: Turn podcasts and RSS into LLM wiki pages.")

# Robust console for legacy Windows (CP950)
def create_console():
    import sys
    # Force safe characters if we are on a legacy Windows terminal
    is_legacy = sys.platform == "win32" and getattr(sys.stdout, "encoding", "").lower() != "utf-8"
    return Console(legacy_windows=is_legacy, safe_box=True)

console = create_console()


@app.command()
def doctor(
    config_path: Path = typer.Option(Path("config/pod2wiki.config.yaml"), "--config", help="Config to check"),
    env_path: Path = typer.Option(Path("config/pod2wiki.env"), "--env-file", help="Env file to check"),
):
    """Check environment and dependencies."""
    console.print("[bold cyan]pod2wiki Doctor - Diagnostic Report[/bold cyan]\n")

    # 1. Python & Package State
    py_ver = sys.version.split()[0]
    console.print(f"Python version: {py_ver} " + ("[green]OK[/green]" if sys.version_info >= (3, 10) else "[red]ERROR: >=3.10 required[/red]"))
    
    try:
        import pod2wiki
        console.print(f"Package 'pod2wiki': [green]INSTALLED[/green] ({Path(pod2wiki.__file__).parent.parent})")
    except ImportError:
        console.print("Package 'pod2wiki': [red]NOT INSTALLED in site-packages[/red] (running from source?)")

    # 2. Dependencies (System)
    console.print("\n[bold]System Binaries:[/bold]")
    def check_bin(name):
        path = shutil.which(name)
        if path:
            console.print(f"  {name}: {path} [green]OK[/green]")
            return True
        else:
            console.print(f"  {name}: [red]NOT FOUND[/red]")
            return False

    check_bin("ffmpeg")
    check_bin("yt-dlp")

    # 3. Config & Env Files
    console.print("\n[bold]Configuration & Files:[/bold]")
    if config_path.is_file():
        try:
            from pod2wiki.cli.fetch_podcasts import load_config
            load_config(config_path)
            console.print(f"  Config: {config_path} [green]READABLE[/green]")
        except Exception as exc:
            console.print(f"  Config: {config_path} [red]INVALID ({exc})[/red]")
    else:
        console.print(f"  Config: {config_path} [yellow]NOT FOUND[/yellow]")

    if env_path.is_file():
        console.print(f"  Env file: {env_path} [green]PRESENT[/green]")
    else:
        console.print(f"  Env file: {env_path} [yellow]NOT FOUND[/yellow]")

    # 4. Path Writability
    console.print("\n[bold]Filesystem:[/bold]")
    def check_writable(p: Path):
        try:
            p.mkdir(parents=True, exist_ok=True)
            test_file = p / ".doctor_test"
            test_file.write_text("test")
            test_file.unlink()
            console.print(f"  Path '{p}': [green]WRITABLE[/green]")
        except Exception as exc:
            console.print(f"  Path '{p}': [red]NOT WRITABLE ({exc})[/red]")

    check_writable(Path("output"))

    # 5. Network & LLM
    console.print("\n[bold]Network & LLM:[/bold]")
    proxy = os.environ.get("PODCAST_PROXY")
    if proxy:
        console.print(f"  PODCAST_PROXY: {proxy} [green]DETECTED[/green]")
    else:
        console.print("  PODCAST_PROXY: [yellow]NOT SET (running direct)[/yellow]")

    try:
        provider_info = resolve_provider()
        console.print(f"  LLM Provider: {provider_info['provider']} [green]OK[/green]")
        console.print(f"  LLM Model: {provider_info['model']} [green]OK[/green]")
        k = provider_info['api_key']
        masked_key = k[:6] + "..." + k[-4:] if len(k) > 10 else "***"
        console.print(f"  API Key: {masked_key} [green]OK[/green]")
    except Exception as exc:
        console.print(f"  LLM Config: [red]FAILED ({exc})[/red]")

    console.print("\n[bold cyan]Diagnosis complete.[/bold cyan]")
    console.print("[bold yellow]Next Step:[/bold yellow] Run 'pod2wiki scan --dry-run' to verify your workflow.")


@app.command()
def init(
    target_dir: Path = typer.Option(Path("."), "--target", help="Target workspace root"),
    wiki_path: Optional[Path] = typer.Option(None, "--wiki", help="Wiki root directory"),
):
    """Interactive setup for a new workspace."""
    console.print("[bold cyan]Setup pod2wiki in your workspace[/bold cyan]\n")
    
    import pod2wiki
    pkg_root = Path(pod2wiki.__file__).parent.parent.parent

    # 1. Config path
    config_dir = target_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "pod2wiki.config.yaml"
    
    if config_file.exists():
        console.print(f"Config already exists at {config_file}. [yellow]Skipping template copy.[/yellow]")
    else:
        # Look for template in package
        template_src = pkg_root / "examples/config.ai-investing.yaml"
        if template_src.exists():
            shutil.copy2(template_src, config_file)
            console.print(f"Created config template at {config_file} [green]OK[/green]")
        else:
            console.print("[red]Could not find config template in package examples/.[/red]")

    # 2. Env path
    env_file = config_dir / "pod2wiki.env"
    if env_file.exists():
        console.print(f"Env file already exists at {env_file}.")
    else:
        env_template = pkg_root / ".env.example"
        if env_template.exists():
            shutil.copy2(env_template, env_file)
            console.print(f"Created env template at {env_file} [green]OK[/green]")

    # 3. Wiki setup
    if wiki_path:
        wiki_root = wiki_path
    else:
        wiki_root = target_dir / "wiki"
    
    for sub in ["sources", "raw/podcasts", "translations"]:
        (wiki_root / sub).mkdir(parents=True, exist_ok=True)
    console.print(f"Wiki directories initialized at {wiki_root} [green]OK[/green]")

    console.print("\n[bold green]Initialization complete![/bold green]")
    console.print(f"[bold yellow]Next steps:[/bold yellow]")
    console.print(f"1. Edit {env_file} with your API keys.")
    console.print(f"2. Run 'pod2wiki doctor' to verify.")
    console.print(f"3. Run 'pod2wiki scan --config {config_file}' to start.")


@app.command()
def test_feed(
    url: str = typer.Argument(..., help="RSS Feed URL or YouTube Channel/Video URL"),
    days: int = typer.Option(1, "--days", help="Days to look back"),
):
    """Validate a single source without running the full pipeline."""
    console.print(f"[bold blue]Testing source:[/bold blue] {url}")
    
    from pod2wiki.models import Config
    from pod2wiki.collect.rss import RSSCollector
    from pod2wiki.collect.youtube import YouTubeCollector
    
    # Mock a minimal config
    cfg = Config(theme="test", channels=[])
    
    async def _test():
        items = []
        if "youtube.com" in url or "youtu.be" in url:
            collector = YouTubeCollector(cfg)
            if "/watch?v=" in url or "youtu.be/" in url:
                items = await collector.collect(days, {}, youtube_mode="urls", explicit_urls=[url])
            else:
                # Treat as channel
                from pod2wiki.models import ChannelConfig
                cfg.channels.append(ChannelConfig(name="Test", youtube=url))
                items = await collector.collect(days, {}, youtube_mode="channels")
        else:
            collector = RSSCollector(cfg)
            # Override feeds for test
            collector.feeds = [{"name": "TestFeed", "url": url}]
            items = await collector.collect(days, {})
            
        if items:
            console.print(f"[green]SUCCESS:[/green] Found {len(items)} items in the last {days} day(s).")
            for i, item in enumerate(items[:3]):
                console.print(f"  {i+1}. {item.title} ({item.date})")
            if len(items) > 3:
                console.print(f"  ... and {len(items)-3} more.")
            console.print("\n[bold yellow]Next Step:[/bold yellow] Add this URL to your config.yaml.")
        else:
            console.print("[yellow]WARNING:[/yellow] No items found. Check if the URL is correct or try increasing --days.")

    asyncio.run(_test())


@app.command()
def scan(
    config_path: Path = typer.Option(..., "--config", help="Path to config.yaml"),
    env_file: Optional[Path] = typer.Option(None, "--env-file", help="Optional .env file"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Runtime output directory"),
    days: Optional[int] = typer.Option(None, "--days", help="Days to look back"),
    wiki_out: Optional[Path] = typer.Option(None, "--wiki-out", help="Wiki root directory"),
    mode: str = typer.Option("all", "--mode", help="Mode: all, rss, youtube, file"),
    input_file: Optional[List[Path]] = typer.Option(None, "--input-file", help="Local files to process"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip LLM calls"),
    translate_full: bool = typer.Option(False, "--translate-full", help="Translate full text"),
    write_insight_log: bool = typer.Option(False, "--write-insight-log", help="Write summary log"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only"),
    retry_failed: Optional[str] = typer.Option(None, "--retry-failed", help="Retry failed items from a previous run ID"),
    resume: Optional[str] = typer.Option(None, "--resume", help="Resume unfinished items from a previous run ID"),
    replay: Optional[str] = typer.Option(None, "--replay", help="Replay all items from a previous run ID using current config/prompts"),
    only: Optional[str] = typer.Option(None, "--only", help="Filter by item ID or title snippet"),
    until_stage: str = typer.Option(None, "--until-stage", help="Stop after: collected, transcribed, summarized"),
):
    """Scan sources and generate wiki pages."""
    from pod2wiki.cli.fetch_podcasts import run_orchestrator
    
    class Args:
        pass
    args = Args()
    args.config = str(config_path)
    args.env_file = str(env_file) if env_file else None
    args.output_dir = str(output_dir) if output_dir else None
    args.days = days
    args.wiki_out = str(wiki_out) if wiki_out else None
    args.mode = mode
    args.input_file = [str(p) for p in input_file] if input_file else []
    args.no_llm = no_llm
    args.translate_full = translate_full
    args.write_insight_log = write_insight_log
    args.dry_run = dry_run
    args.retry_failed = retry_failed
    args.resume = resume
    args.replay = replay
    args.only = only
    args.until_stage = until_stage
    
    # Defaults
    args.domain = "investing"
    args.locale = "zh-CN"
    args.days_quick = False
    args.title = None
    args.channel = None
    args.source_url = None
    args.date = None
    args.max_items = None
    args.max_items_per_feed = None
    args.youtube_mode = "all"
    args.youtube_url = []
    args.youtube_query = []
    args.youtube_max_results = None
    args.transcript_backend = "auto"
    args.transcript_languages = "en,en-US,en-GB,zh-Hans,zh"
    args.transcript_sleep = 1.5
    args.whisper_model = None
    args.whisper_clip_seconds = None
    args.no_whisper = False
    args.whisper_threshold = None
    args.translation_locale = "zh-CN"
    args.insight_log = None

    asyncio.run(run_orchestrator(args))


@app.command()
def watch(
    config_path: Path = typer.Option(..., "--config", help="Path to config.yaml"),
    interval: int = typer.Option(4, "--interval", help="Interval in hours between scans"),
    env_file: Optional[Path] = typer.Option(None, "--env-file"),
    wiki_out: Optional[Path] = typer.Option(None, "--wiki-out"),
):
    """Run in watch mode: periodically scan sources for new content."""
    from pod2wiki.cli.fetch_podcasts import run_orchestrator
    
    class Args:
        pass
    args = Args()
    args.config = str(config_path)
    args.env_file = str(env_file) if env_file else None
    args.wiki_out = str(wiki_out) if wiki_out else None
    args.output_dir = "output"
    args.mode = "all"
    args.days = 1 # Quick lookback for frequent watches
    args.no_llm = False
    args.translate_full = False
    args.write_insight_log = True
    args.dry_run = False
    # ... other defaults
    args.domain = "investing"
    args.locale = "zh-CN"
    args.translation_locale = "zh-CN"
    args.input_file = []
    args.retry_failed = None
    args.resume = None
    args.replay = None
    args.only = None
    args.until_stage = None
    args.youtube_max_results = 3
    args.max_items = None
    args.max_items_per_feed = 3
    args.youtube_mode = "all"
    args.youtube_url = []
    args.youtube_query = []
    args.transcript_backend = "auto"
    args.transcript_languages = "en,en-US,en-GB,zh-Hans,zh"
    args.transcript_sleep = 1.5
    args.whisper_model = None
    args.whisper_clip_seconds = None
    args.no_whisper = False
    args.whisper_threshold = None
    args.insight_log = None
    args.days_quick = False
    args.title = None
    args.channel = None
    args.source_url = None
    args.date = None

    async def _loop():
        console.print(f"[bold green]Watch mode active.[/bold green] Interval: {interval}h")
        while True:
            console.print(f"\n[bold blue]Starting scheduled scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/bold blue]")
            try:
                await run_orchestrator(args)
            except Exception as exc:
                console.print(f"[red]Scheduled scan failed: {exc}[/red]")
            
            console.print(f"[yellow]Sleeping for {interval} hours...[/yellow]")
            await asyncio.sleep(interval * 3600)

    try:
        asyncio.run(_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch mode stopped by user.[/yellow]")


@app.command()
def replay(
    run_id: str = typer.Argument(..., help="Run ID to replay"),
    config_path: Path = typer.Option(..., "--config", help="Path to config.yaml"),
    env_file: Optional[Path] = typer.Option(None, "--env-file"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir"),
    no_llm: bool = typer.Option(False, "--no-llm"),
):
    """Shortcut to replay a specific run ID."""
    from pod2wiki.cli.fetch_podcasts import run_orchestrator
    class Args:
        pass
    args = Args()
    args.replay = run_id
    args.config = str(config_path)
    args.env_file = str(env_file) if env_file else None
    args.output_dir = str(output_dir) if output_dir else None
    args.no_llm = no_llm
    
    # Defaults
    args.wiki_out = "wiki"
    args.mode = "all"
    args.input_file = []
    args.days = 7
    args.translate_full = False
    args.write_insight_log = True
    args.dry_run = False
    args.domain = "investing"
    args.locale = "zh-CN"
    args.translation_locale = "zh-CN"
    args.retry_failed = None
    args.resume = None
    args.only = None
    args.until_stage = None
    args.youtube_max_results = None
    args.max_items = None
    args.max_items_per_feed = None
    args.youtube_mode = "all"
    args.youtube_url = []
    args.youtube_query = []
    args.transcript_backend = "auto"
    args.transcript_languages = "en,en-US,en-GB,zh-Hans,zh"
    args.transcript_sleep = 1.5
    args.whisper_model = None
    args.whisper_clip_seconds = None
    args.no_whisper = False
    args.whisper_threshold = None
    args.insight_log = None
    args.days_quick = False
    args.title = None
    args.channel = None
    args.source_url = None
    args.date = None

    asyncio.run(run_orchestrator(args))


@app.command(name="runs")
def list_runs(
    output_dir: Path = typer.Option(Path("output"), "--output-dir", help="Output directory containing pod2wiki_v1.db"),
    limit: int = typer.Option(10, "--limit", help="Number of runs to show"),
):
    """List historical run records."""
    from pod2wiki.persistence.state import RunStateManager
    db_path = output_dir / "pod2wiki_v1.db"
    if not db_path.exists():
        console.print(f"[yellow]No run history found at {db_path}[/yellow]")
        return

    state_mgr = RunStateManager(db_path)
    runs = state_mgr.get_recent_runs(limit)

    table = Table(title="Recent pod2wiki Runs")
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Started", style="magenta")
    table.add_column("Provider/Model", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Items", justify="right")
    table.add_column("Failed", justify="right", style="red")

    for r in runs:
        status_style = "green" if r["status"] == "completed" else "yellow"
        table.add_row(
            r["id"],
            r["start_time"],
            f"{r['provider']}/{r['model']}",
            f"[{status_style}]{r['status']}[/{status_style}]",
            str(r["total_items"]),
            str(r["failed_items"]),
        )
    console.print(table)
    console.print("\nUse 'pod2wiki runs-show <run-id>' for details.")


@app.command(name="runs-show")
def show_run(
    run_id: str = typer.Argument(..., help="The Run ID to inspect"),
    output_dir: Path = typer.Option(Path("output"), "--output-dir", help="Output directory"),
    show_events: bool = typer.Option(False, "--events", help="Show all lifecycle events for items"),
    show_warnings: bool = typer.Option(False, "--warnings", help="Show detailed warnings per item"),
):
    """Show detailed status of items in a specific run."""
    from pod2wiki.persistence.state import RunStateManager
    state_mgr = RunStateManager(output_dir / "pod2wiki_v1.db")
    details = state_mgr.get_run_details(run_id)
    
    if not details:
        console.print(f"[red]Run ID {run_id} not found.[/red]")
        return

    table = Table(title=f"Details for Run: {run_id}")
    table.add_column("Item Title", style="cyan")
    table.add_column("Channel", style="magenta")
    table.add_column("Stage", style="bold")
    table.add_column("Error/Message", style="red")

    for d in details:
        stage_style = "green" if d["stage"] == "written" else "yellow"
        if d["stage"] == "failed": stage_style = "red"
        table.add_row(
            d["title"][:50],
            d["channel"],
            f"[{stage_style}]{d['stage']}[/{stage_style}]",
            d["error_msg"] or "",
        )
    console.print(table)

    if show_events:
        console.print("\n[bold cyan]Lifecycle Events:[/bold cyan]")
        events = state_mgr.get_run_events(run_id)
        ev_table = Table()
        ev_table.add_column("Timestamp")
        ev_table.add_column("Item Title")
        ev_table.add_column("Stage")
        ev_table.add_column("Message")
        for ev in events:
            # Map item title from details
            title = next((d["title"] for d in details if d["item_id"] == ev["item_id"]), "Unknown")
            ev_table.add_row(ev["timestamp"], title[:30], ev["stage"], ev["message"] or "")
        console.print(ev_table)

    if show_warnings:
        console.print("\n[bold yellow]Warnings Found:[/bold yellow]")
        warnings = state_mgr.get_run_warnings(run_id)
        if not warnings:
            console.print("  None")
        else:
            warn_table = Table()
            warn_table.add_column("Item Title")
            warn_table.add_column("Type", style="bold red")
            warn_table.add_column("Message")
            for w in warnings:
                title = next((d["title"] for d in details if d["item_id"] == w["item_id"]), "Unknown")
                warn_table.add_row(title[:30], w["type"], w["message"])
            console.print(warn_table)


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8080, "--port", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (development)"),
):
    """Start the local web console."""
    import uvicorn
    console.print(f"[bold green]Starting pod2wiki web console on http://{host}:{port}[/bold green]")
    uvicorn.run("pod2wiki.web.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
