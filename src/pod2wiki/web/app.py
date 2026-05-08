"""FastAPI application for the pod2wiki local web console."""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Request, Form, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from pod2wiki.persistence.state import RunStateManager
from pod2wiki.cli.fetch_podcasts import run_orchestrator, load_config
from pod2wiki.reporting.estimator import CostEstimator
from pod2wiki.models import Config
from pod2wiki.web.auth import get_current_user, hash_password, verify_password

app = FastAPI(title="pod2wiki Web Console")

# Templates setup
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Dependency injection for StateManager
def get_state_mgr():
    output_dir = Path(os.environ.get("POD2WIKI_OUTPUT", "output"))
    return RunStateManager(output_dir / "pod2wiki_v1.db")

async def auth_user(request: Request, state_mgr: RunStateManager = Depends(get_state_mgr)):
    try:
        user = await get_current_user(request, state_mgr)
        return user
    except HTTPException:
        raise

@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def unauthorized_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, state_mgr: RunStateManager = Depends(get_state_mgr)):
    users = state_mgr.list_users()
    return templates.TemplateResponse(
        request=request, name="login.html", context={"has_users": len(users) > 0}
    )

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    state_mgr: RunStateManager = Depends(get_state_mgr),
):
    users = state_mgr.list_users()
    user = state_mgr.get_user(username)

    if not users:
        # First time setup: create Admin
        state_mgr.create_user(username, hash_password(password), role="admin")
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="pod2wiki_session", value=username)
        return response

    if user and verify_password(password, user["password_hash"]):
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="pod2wiki_session", value=username)
        return response

    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": "Invalid credentials", "has_users": True}
    )

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("pod2wiki_session")
    return response

@app.get("/users", response_class=HTMLResponse)
async def manage_users(request: Request, user: dict = Depends(auth_user), state_mgr: RunStateManager = Depends(get_state_mgr)):
    if not user: return RedirectResponse(url="/login", status_code=303)
    user_list = state_mgr.list_users()
    return templates.TemplateResponse(
        request=request, name="users.html", context={"user": user, "user_list": user_list}
    )

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(auth_user)):
    if not user: return RedirectResponse(url="/login", status_code=303)
    state_mgr = get_state_mgr()
    recent_runs = state_mgr.get_recent_runs(limit=5)
    
    # Parse command_args for each run
    for r in recent_runs:
        if isinstance(r.get("command_args"), str):
            try: r["command_args"] = json.loads(r["command_args"])
            except json.JSONDecodeError: r["command_args"] = {}

    last_run = recent_runs[0] if recent_runs else None
    active_run = state_mgr.get_active_run()
    if active_run and isinstance(active_run.get("command_args"), str):
        try: active_run["command_args"] = json.loads(active_run["command_args"])
        except json.JSONDecodeError: active_run["command_args"] = {}

    all_warnings = []
    if last_run:
        all_warnings = state_mgr.get_run_warnings(last_run["id"])[:5]

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "user": user,
            "recent_runs": recent_runs, 
            "last_run": last_run,
            "active_run": active_run,
            "recent_warnings": all_warnings
        }
    )


@app.get("/api/dashboard/active-run", response_class=HTMLResponse)
async def active_run_fragment(request: Request, user: dict = Depends(auth_user)):
    if not user: return HTMLResponse("")
    state_mgr = get_state_mgr()
    active_run = state_mgr.get_active_run()
    if active_run and isinstance(active_run.get("command_args"), str):
        try: active_run["command_args"] = json.loads(active_run["command_args"])
        except json.JSONDecodeError: active_run["command_args"] = {}
    
    return templates.TemplateResponse(
        request=request,
        name="partials/active_run_card.html",
        context={"active_run": active_run},
    )


@app.get("/runs", response_class=HTMLResponse)
async def list_runs(
    request: Request,
    user: dict = Depends(auth_user),
    limit: int = 20,
    q: str = "",
    status_filter: str = "",
):
    if not user: return RedirectResponse(url="/login", status_code=303)
    state_mgr = get_state_mgr()
    runs = state_mgr.get_recent_runs(limit=limit)
    for r in runs:
        if isinstance(r.get("command_args"), str):
            try:
                r["command_args"] = json.loads(r["command_args"])
            except json.JSONDecodeError:
                r["command_args"] = {}
    query = q.strip().lower()
    selected_status = status_filter.strip().lower()
    if query:
        runs = [
            r for r in runs
            if query in r["id"].lower()
            or query in str(r.get("provider", "")).lower()
            or query in str(r.get("model", "")).lower()
            or query in str(r.get("command_args", {}).get("wiki_out", "")).lower()
            or query in str(r.get("command_args", {}).get("output_dir", "")).lower()
        ]
    if selected_status:
        runs = [r for r in runs if str(r.get("status", "")).lower() == selected_status]
    return templates.TemplateResponse(
        request=request,
        name="runs.html",
        context={
            "user": user,
            "runs": runs,
            "filters": {"q": q, "status_filter": status_filter, "limit": limit},
        },
    )


@app.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_details(request: Request, run_id: str, user: dict = Depends(auth_user)):
    if not user: return RedirectResponse(url="/login", status_code=303)
    state_mgr = get_state_mgr()
    items = state_mgr.get_run_details(run_id)
    events = state_mgr.get_run_events(run_id)
    warnings = state_mgr.get_run_warnings(run_id)
    return templates.TemplateResponse(
        request=request,
        name="run_details.html",
        context={
            "user": user,
            "run_id": run_id,
            "items": items,
            "events": events,
            "warnings": warnings,
        },
    )


@app.get("/sources", response_class=HTMLResponse)
async def list_sources(request: Request, user: dict = Depends(auth_user)):
    if not user: return RedirectResponse(url="/login", status_code=303)
    cfg_path = Path(os.environ.get("POD2WIKI_CONFIG", "config/pod2wiki.config.yaml"))
    import yaml
    
    # Load starter packs
    packs = {}
    pack_path = Path(__file__).parent.parent.parent.parent / "examples/starter-packs.yaml"
    if pack_path.exists():
        packs = yaml.safe_load(pack_path.read_text(encoding="utf-8"))

    if not cfg_path.exists():
        return templates.TemplateResponse(request=request, name="sources.html", context={"user": user, "error": "Config not found", "channels": [], "blog_feeds": [], "search_queries": [], "packs": packs})
    
    config = load_config(cfg_path)
    return templates.TemplateResponse(
        request=request, 
        name="sources.html", 
        context={
            "user": user,
            "channels": config.channels, 
            "blog_feeds": config.blog_feeds,
            "search_queries": config.youtube_search_queries,
            "packs": packs
        }
    )


@app.post("/sources/add", response_class=RedirectResponse)
async def add_source(
    user: dict = Depends(auth_user),
    name: str = Form(None),
    url: str = Form(None),
    kind: str = Form("youtube"), # youtube, rss, search
):
    if not user: return RedirectResponse(url="/login", status_code=303)
    cfg_path = Path(os.environ.get("POD2WIKI_CONFIG", "config/pod2wiki.config.yaml"))
    import yaml
    from pod2wiki.models import ChannelConfig
    
    config = load_config(cfg_path)
    if kind == "youtube":
        config.channels.append(ChannelConfig(name=name, youtube=url))
    elif kind == "rss":
        config.blog_feeds.append({"name": name, "url": url, "author": user["username"]})
    elif kind == "search":
        config.youtube_search_queries.append(url) # url used as query in this case
    
    cfg_path.write_text(yaml.dump(config.model_dump(), allow_unicode=True), encoding="utf-8")
    return RedirectResponse(url="/sources", status_code=303)


@app.post("/sources/apply-pack", response_class=RedirectResponse)
async def apply_starter_pack(user: dict = Depends(auth_user), pack_id: str = Form(...)):
    if not user: return RedirectResponse(url="/login", status_code=303)
    cfg_path = Path(os.environ.get("POD2WIKI_CONFIG", "config/pod2wiki.config.yaml"))
    pack_path = Path(__file__).parent.parent.parent.parent / "examples/starter-packs.yaml"
    import yaml
    from pod2wiki.models import ChannelConfig
    
    if not pack_path.exists(): return RedirectResponse(url="/sources", status_code=303)
    packs = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    pack = packs.get(pack_id)
    if not pack: return RedirectResponse(url="/sources", status_code=303)

    config = load_config(cfg_path)
    for ch in pack.get("channels", []):
        if not any(c.youtube == ch["youtube"] for c in config.channels):
            config.channels.append(ChannelConfig(**ch))
    for bf in pack.get("blog_feeds", []):
        if not any(f["url"] == bf["url"] for f in config.blog_feeds):
            config.blog_feeds.append(bf)
    
    cfg_path.write_text(yaml.dump(config.model_dump(), allow_unicode=True), encoding="utf-8")
    return RedirectResponse(url="/sources", status_code=303)


@app.post("/sources/delete", response_class=RedirectResponse)
async def delete_source(
    user: dict = Depends(auth_user),
    index: int = Form(...),
    kind: str = Form(...), # youtube, rss, search
):
    if not user: return RedirectResponse(url="/login", status_code=303)
    cfg_path = Path(os.environ.get("POD2WIKI_CONFIG", "config/pod2wiki.config.yaml"))
    import yaml
    config = load_config(cfg_path)
    
    if kind == "youtube" and 0 <= index < len(config.channels):
        config.channels.pop(index)
    elif kind == "rss" and 0 <= index < len(config.blog_feeds):
        config.blog_feeds.pop(index)
    elif kind == "search" and 0 <= index < len(config.youtube_search_queries):
        config.youtube_search_queries.pop(index)
    
    cfg_path.write_text(yaml.dump(config.model_dump(), allow_unicode=True), encoding="utf-8")
    return RedirectResponse(url="/sources", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: dict = Depends(auth_user)):
    if not user: return RedirectResponse(url="/login", status_code=303)
    cfg_path = Path(os.environ.get("POD2WIKI_CONFIG", "config/pod2wiki.config.yaml"))
    env_path = Path(os.environ.get("POD2WIKI_ENV", "config/pod2wiki.env"))
    
    config = load_config(cfg_path) if cfg_path.exists() else Config()

    env_data = ""
    if env_path.exists():
        env_data = env_path.read_text(encoding="utf-8")

    return templates.TemplateResponse(
        request=request, 
        name="settings.html", 
        context={
            "user": user,
            "config": config, 
            "env": env_data, 
            "paths": {"config": cfg_path, "env": env_path},
            "os_environ": os.environ
        }
    )


@app.post("/settings/update", response_class=RedirectResponse)
async def update_settings(
    user: dict = Depends(auth_user),
    provider: str = Form(...),
    model: str = Form(...),
    max_tokens: int = Form(...),
    wiki_out: str = Form(...),
    whisper_model: str = Form(...),
    whisper_clip: int = Form(...),
    whisper_threshold: int = Form(...),
    proxy: Optional[str] = Form(None),
):
    if not user: return RedirectResponse(url="/login", status_code=303)
    cfg_path = Path(os.environ.get("POD2WIKI_CONFIG", "config/pod2wiki.config.yaml"))
    import yaml
    config = load_config(cfg_path)
    
    config.llm.provider = provider
    config.llm.model = model
    config.llm.max_tokens = max_tokens
    config.wiki_root = wiki_out
    config.whisper.model = whisper_model
    config.whisper.clip_seconds = whisper_clip
    config.whisper.auto_threshold = whisper_threshold
    
    if proxy:
        os.environ["PODCAST_PROXY"] = proxy
    elif "PODCAST_PROXY" in os.environ:
        del os.environ["PODCAST_PROXY"]
    
    cfg_path.write_text(yaml.dump(config.model_dump(), allow_unicode=True), encoding="utf-8")
    return RedirectResponse(url="/settings", status_code=303)


@app.get("/preview", response_class=HTMLResponse)
async def preview_list(
    request: Request,
    user: dict = Depends(auth_user),
    q: str = "",
    review_status: str = "",
):
    if not user: return RedirectResponse(url="/login", status_code=303)
    output_dir = Path(os.environ.get("POD2WIKI_OUTPUT", "output"))
    state_mgr = get_state_mgr()
    
    def get_files(subdir):
        d = output_dir / subdir
        if not d.exists(): return []
        return sorted(list(d.glob("*.md")), key=os.path.getmtime, reverse=True)[:20]

    query = q.strip().lower()
    selected_review_status = review_status.strip().lower()
    review_map = {row["item_id"]: row for row in state_mgr.list_item_reviews()}

    sources = get_files("sources")
    raw = get_files("raw/podcasts")
    if query:
        sources = [path for path in sources if query in path.name.lower()]
        raw = [path for path in raw if query in path.name.lower()]
    all_translation_entries = []
    for file_path in get_files("translations"):
        review = review_map.get(file_path.name, {"status": "pending", "notes": ""})
        all_translation_entries.append({"file": file_path, "review": review})
    translation_entries = all_translation_entries
    if query:
        translation_entries = [entry for entry in translation_entries if query in entry["file"].name.lower()]
    if selected_review_status:
        translation_entries = [
            entry for entry in translation_entries
            if str(entry["review"].get("status", "pending")).lower() == selected_review_status
        ]
    review_counts = {
        "pending": len([entry for entry in all_translation_entries if entry["review"].get("status", "pending") == "pending"]),
        "accepted": len([entry for entry in all_translation_entries if entry["review"].get("status") == "accepted"]),
        "rejected": len([entry for entry in all_translation_entries if entry["review"].get("status") == "rejected"]),
    }
    pending_review_entries = [entry for entry in all_translation_entries if entry["review"].get("status", "pending") == "pending"][:8]

    return templates.TemplateResponse(
        request=request, 
        name="preview_list.html", 
        context={
            "user": user,
            "sources": sources,
            "raw": raw,
            "translations": [entry["file"] for entry in translation_entries],
            "translation_entries": translation_entries,
            "pending_review_entries": pending_review_entries,
            "review_counts": review_counts,
            "filters": {"q": q, "review_status": review_status},
            "insight_log": output_dir / "ai-insights-log.md" if (output_dir / "ai-insights-log.md").exists() else None
        }
    )


@app.get("/preview/{category}/{filename}", response_class=HTMLResponse)
async def preview_file(request: Request, category: str, filename: str, user: dict = Depends(auth_user)):
    if not user: return RedirectResponse(url="/login", status_code=303)
    output_dir = Path(os.environ.get("POD2WIKI_OUTPUT", "output"))
    state_mgr = get_state_mgr()
    
    path_map = {
        "sources": output_dir / "sources" / filename,
        "raw": output_dir / "raw/podcasts" / filename,
        "translations": output_dir / "translations" / filename,
        "log": output_dir / filename # for ai-insights-log.md
    }
    
    file_path = path_map.get(category)
    if not file_path or not file_path.exists():
        return HTMLResponse("File not found", status_code=404)
    
    content = file_path.read_text(encoding="utf-8", errors="replace")
    
    # Side-by-side logic: if translation, find raw
    original_content = None
    item_id = None
    review = {"status": "pending", "notes": ""}

    if category == "translations":
        import re
        raw_name = re.sub(r"\.[a-z]{2}(-[A-Z]{2})?\.md$", ".md", filename)
        raw_path = output_dir / "raw/podcasts" / raw_name
        if raw_path.exists():
            original_content = raw_path.read_text(encoding="utf-8", errors="replace")
        item_id = filename # temporary fallback

    if item_id:
        review = state_mgr.get_item_review(item_id)

    # Video preview logic
    video_id = None
    if "youtube" in content.lower() or category == "raw":
        import re
        vid_match = re.search(r"-([a-zA-Z0-9_-]{11})\.md$", filename)
        if vid_match:
            video_id = vid_match.group(1)
        else:
            vid_content_match = re.search(r"watch\?v=([a-zA-Z0-9_-]{11})", content)
            if vid_content_match:
                video_id = vid_content_match.group(1)

    return templates.TemplateResponse(
        request=request, 
        name="preview_file.html", 
        context={
            "user": user,
            "filename": filename, 
            "content": content, 
            "original_content": original_content,
            "category": category,
            "item_id": item_id,
            "review": review,
            "video_id": video_id
        }
    )


@app.post("/api/review/{item_id}", response_class=HTMLResponse)
async def update_review(
    request: Request,
    item_id: str,
    status: str = Form(...),
    notes: Optional[str] = Form(None),
    user: dict = Depends(auth_user),
):
    if not user: return HTMLResponse("")
    state_mgr = get_state_mgr()
    state_mgr.update_review_status(item_id, status, notes)
    return templates.TemplateResponse(
        request=request,
        name="partials/review_status_badge.html",
        context={"status": status, "notes": notes, "item_id": item_id},
    )

@app.get("/scan", response_class=HTMLResponse)
async def scan_form(request: Request, user: dict = Depends(auth_user)):
    if not user: return RedirectResponse(url="/login", status_code=303)
    cfg_path = Path(os.environ.get("POD2WIKI_CONFIG", "config/pod2wiki.config.yaml"))
    config = load_config(cfg_path) if cfg_path.exists() else Config()
    return templates.TemplateResponse(
        request=request, 
        name="scan_form.html", 
        context={"user": user, "config": config, "presets": config.presets}
    )


@app.post("/scan/presets/save", response_class=RedirectResponse)
async def save_preset(
    user: dict = Depends(auth_user),
    name: str = Form(...),
    mode: str = Form("all"),
    days: int = Form(7),
    no_llm: bool = Form(False),
    translate_full: bool = Form(False),
    config_path: str = Form("config/pod2wiki.config.yaml"),
    wiki_out: str = Form("wiki"),
):
    if not user: return RedirectResponse(url="/login", status_code=303)
    cfg_path = Path(os.environ.get("POD2WIKI_CONFIG", "config/pod2wiki.config.yaml"))
    import yaml
    config = load_config(cfg_path)

    config.presets[name] = {
        "mode": mode,
        "days": days,
        "no_llm": no_llm,
        "translate_full": translate_full,
        "config_path": config_path,
        "wiki_out": wiki_out,
    }

    cfg_path.write_text(yaml.dump(config.model_dump(), allow_unicode=True), encoding="utf-8")
    return RedirectResponse(url="/scan", status_code=303)


@app.post("/scan")
async def start_scan(
    background_tasks: BackgroundTasks,
    user: dict = Depends(auth_user),
    mode: str = Form("all"),
    days: int = Form(7),
    no_llm: bool = Form(False),
    translate_full: bool = Form(False),
    config_path: str = Form("config/pod2wiki.config.yaml"),
    env_file: str = Form("config/pod2wiki.env"),
    output_dir: str = Form("output"),
    wiki_out: str = Form("wiki"),
    input_files: Optional[str] = Form(None),
):
    if not user: return RedirectResponse(url="/login", status_code=303)
    # Map form fields to Args object for orchestrator
    class Args:
        pass
    args = Args()
    args.config = config_path
    args.env_file = env_file
    args.output_dir = output_dir
    args.wiki_out = wiki_out
    args.mode = mode
    args.days = days
    args.no_llm = no_llm
    args.translate_full = translate_full
    args.input_file = [f.strip() for f in input_files.split(",")] if input_files else []
    
    # Defaults
    args.domain = "investing"
    args.locale = "zh-CN"
    args.translation_locale = "zh-CN"
    args.write_insight_log = True
    args.dry_run = False
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

    background_tasks.add_task(run_orchestrator, args)
    return RedirectResponse(url="/runs", status_code=303)


@app.post("/api/scan/estimate", response_class=HTMLResponse)
async def estimate_scan(
    request: Request,
    user: dict = Depends(auth_user),
    mode: str = Form("all"),
    days: int = Form(7),
    no_llm: bool = Form(False),
    translate_full: bool = Form(False),
    config_path: str = Form("config/pod2wiki.config.yaml"),
    input_files: Optional[str] = Form(None),
):
    if not user: return HTMLResponse("")
    cfg_path = Path(config_path)
    config = load_config(cfg_path) if cfg_path.exists() else Config()
    
    # Mock args for estimator
    class Args:
        pass
    args = Args()
    args.mode = mode
    args.days = days
    args.no_llm = no_llm
    args.translate_full = translate_full
    args.input_file = [f.strip() for f in input_files.split(",")] if input_files else []
    args.max_items = None
    args.write_insight_log = True
    
    estimator = CostEstimator(config)
    report = estimator.estimate(args)
    
    return templates.TemplateResponse(
        request=request,
        name="partials/scan_estimate.html",
        context={"report": report}
    )


# HTMX endpoint for status polling
@app.get("/api/runs/{run_id}/status")
async def run_status_fragment(request: Request, run_id: str, user: dict = Depends(auth_user)):
    if not user: return HTMLResponse("")
    state_mgr = get_state_mgr()
    items = state_mgr.get_run_details(run_id)
    # Simple summary counts
    total = len(items)
    written = len([i for i in items if i["stage"] == "written"])
    failed = len([i for i in items if i["stage"] == "failed"])
    
    return templates.TemplateResponse(
        request=request,
        name="partials/run_status.html",
        context={"run_id": run_id, "total": total, "written": written, "failed": failed},
    )


@app.get("/api/runs/{run_id}/items")
async def run_items_fragment(request: Request, run_id: str, user: dict = Depends(auth_user)):
    if not user: return HTMLResponse("")
    state_mgr = get_state_mgr()
    items = state_mgr.get_run_details(run_id)
    return templates.TemplateResponse(
        request=request,
        name="partials/run_items.html",
        context={"items": items},
    )
