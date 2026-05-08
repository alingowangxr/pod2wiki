# pod2wiki Usage Guide

This guide explains how to install, configure, run, and operate `pod2wiki` in day-to-day use.

## What pod2wiki does

`pod2wiki` collects content from:

- YouTube channels and videos
- RSS feeds and blog feeds
- local transcript or markdown files

It then:

- fetches subtitles or source text
- optionally runs Whisper transcription
- summarizes content with an LLM
- optionally translates full text
- writes markdown outputs into your wiki and output directories
- keeps run history, warnings, recovery state, and review state in SQLite

Main entry points:

- CLI: [src/pod2wiki/cli/main.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/cli/main.py:1)
- Orchestrator: [src/pod2wiki/cli/fetch_podcasts.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/cli/fetch_podcasts.py:1)
- Web Console: [src/pod2wiki/web/app.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/web/app.py:1)
- Default config: [config/pod2wiki.config.yaml](/C:/Users/szmik/pod2wiki/config/pod2wiki.config.yaml:1)
- Env config: [config/pod2wiki.env](/C:/Users/szmik/pod2wiki/config/pod2wiki.env:1)

## Prerequisites

You should have:

- Python 3.10+
- `ffmpeg`
- `yt-dlp`
- an LLM API key or a local LLM endpoint
- optional: `faster-whisper` if you want Whisper transcription

Install the package in editable mode:

```bash
pip install -e .
```

If you prefer a plain checkout without package install:

```bash
PYTHONPATH=src python -m pod2wiki.cli.main --help
```

## Initial setup

Initialize a workspace:

```bash
pod2wiki init --target .
```

This creates:

- `config/pod2wiki.config.yaml`
- `config/pod2wiki.env`
- `wiki/sources/`
- `wiki/raw/podcasts/`
- `wiki/translations/`

Then run diagnostics:

```bash
pod2wiki doctor
```

Recommended first validation:

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --days 1 --dry-run
```

## Configuration

### Main config

The main config file is:

- [config/pod2wiki.config.yaml](/C:/Users/szmik/pod2wiki/config/pod2wiki.config.yaml:1)

Common fields:

- `theme`
- `days_lookback`
- `max_items_per_feed`
- `max_videos_per_channel`
- `max_transcript_chars`
- `whisper.enabled`
- `whisper.model`
- `whisper.clip_seconds`
- `whisper.auto_threshold`
- `llm.provider`
- `llm.model`
- `llm.max_tokens`
- `channels`
- `people_searches`
- `exec_searches`
- `youtube_urls`
- `blog_feeds`
- `hypotheses`
- `reversal_triggers`
- `presets`
- `post_processors`

### LLM and proxy env

Environment settings live in:

- [config/pod2wiki.env](/C:/Users/szmik/pod2wiki/config/pod2wiki.env:1)

Common variables:

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`
- `PODCAST_PROXY`

Supported provider presets in the sample env include:

- DeepSeek
- Kimi / Moonshot
- GLM
- Qwen
- OpenAI
- Gemini
- Ollama

## Common CLI commands

### Environment check

```bash
pod2wiki doctor
```

Checks:

- Python version
- package availability
- `ffmpeg`
- `yt-dlp`
- config readability
- env presence
- LLM config
- proxy detection
- output path writability

### Validate one source

```bash
pod2wiki test-feed "https://www.youtube.com/@DwarkeshPatel/videos" --days 1
pod2wiki test-feed "https://www.dwarkesh.com/feed" --days 1
```

### Dry-run

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --days 1 --dry-run
```

This does not run the full pipeline. It estimates workload, LLM usage, transcription usage, and risk.

### Real scan

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --days 7 --write-insight-log
```

Useful variants:

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --mode rss
pod2wiki scan --config config/pod2wiki.config.yaml --mode youtube
pod2wiki scan --config config/pod2wiki.config.yaml --mode file --input-file examples/sample-transcript.md
pod2wiki scan --config config/pod2wiki.config.yaml --no-llm
pod2wiki scan --config config/pod2wiki.config.yaml --translate-full
pod2wiki scan --config config/pod2wiki.config.yaml --wiki-out wiki
pod2wiki scan --config config/pod2wiki.config.yaml --output-dir output
```

Supported modes:

- `all`
- `rss`
- `youtube`
- `file`

### Recovery and replay

Resume unfinished work:

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --resume <run-id>
```

Retry only failed items:

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --retry-failed <run-id>
```

Replay all items from a previous run:

```bash
pod2wiki replay <run-id> --config config/pod2wiki.config.yaml
```

### Watch mode

Run scheduled repeated scans:

```bash
pod2wiki watch --config config/pod2wiki.config.yaml --interval 4
```

This runs a new scan every 4 hours using a short lookback window.

### Run history

List recent runs:

```bash
pod2wiki runs
```

Show one run:

```bash
pod2wiki runs-show <run-id>
```

Show warnings:

```bash
pod2wiki runs-show <run-id> --warnings
```

Show event timeline:

```bash
pod2wiki runs-show <run-id> --events
```

## Working with local files

If you already have transcripts or markdown files:

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --mode file --input-file examples/sample-transcript.md --no-llm
```

You can pass multiple `--input-file` arguments.

## Web Console

Start the web UI:

```bash
pod2wiki ui --host 127.0.0.1 --port 8080
```

Open:

- `http://127.0.0.1:8080`

### Authentication

The web console supports local multi-user login.

First-time behavior:

- opening `/login` shows first-time setup
- the first successful login creates an admin user
- subsequent logins use the stored user table and session cookie

Main auth-related pages:

- `/login`
- `/logout`
- `/users`

### Dashboard

The dashboard shows:

- active run status
- last run summary
- success / failed / skipped / warning counts
- output locations
- recent warnings
- recent run history

### Runs

The Runs page supports:

- run history
- duration
- success / failed / skipped / warning counts
- expandable item-level details
- direct access to run detail pages

### Sources

The Sources page supports:

- adding YouTube channels
- adding RSS/blog feeds
- adding YouTube search queries
- deleting sources
- applying starter source packs

### Scan form

The Scan page supports:

- mode
- days
- config path
- env path
- output path
- wiki path
- local input files
- no-LLM mode
- full translation
- pre-run cost estimation
- saved presets

### Settings

The Settings page supports:

- LLM provider
- LLM model
- max tokens
- wiki root
- Whisper model
- Whisper clip seconds
- Whisper auto threshold
- SOCKS5 proxy

### Preview

The Preview page supports:

- source summary preview
- raw transcript preview
- translation preview
- insight log preview

For translations it also supports:

- side-by-side raw vs translated view
- review status
- review notes
- accept / reject / pending workflow

For YouTube-linked content it also supports:

- embedded video preview
- thumbnail / frame gallery

## Output structure

The main outputs live in:

- `output/`
- `wiki/`

Typical output files:

- `output/pod2wiki_v1.db`
- `output/sources/*.md`
- `output/raw/podcasts/*.md`
- `output/translations/*.md`
- `output/ai-insights-log.md`
- `output/index.md`

If `wiki_out` is enabled, synchronized copies are written to:

- `wiki/sources/*.md`
- `wiki/raw/podcasts/*.md`
- `wiki/translations/*.md`

### File meaning

- `sources/*.md`: summarized source pages
- `raw/podcasts/*.md`: original full text or transcript
- `translations/*.md`: full translations
- `ai-insights-log.md`: run-level synthesized insight log
- `index.md`: generated run index from post-processors

## Post-processors

`pod2wiki` supports plugin-style post-processing.

Config field:

```yaml
post_processors:
  - "your_module.path:YourProcessorClass"
```

Behavior:

- built-in processors run first
- configured processors are imported dynamically
- each processor receives processed items, config, and output dir

Implementation:

- [src/pod2wiki/processing/post.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/processing/post.py:1)

## Presets

The web scan form supports:

- saving current scan form values as a preset
- loading saved presets back into the form

Preset data is stored under `config.presets`.

## Translation review workflow

The translation review workflow supports:

- side-by-side original and translation
- review state persistence in SQLite
- statuses:
  - `accepted`
  - `rejected`
  - `pending`
- review notes

This is useful for marking translations that should be kept, flagged, or rerun later.

## Recommended daily workflow

First-time setup:

```bash
pod2wiki init --target .
pod2wiki doctor
pod2wiki scan --config config/pod2wiki.config.yaml --days 1 --dry-run
pod2wiki ui
```

Normal weekly run:

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --days 7 --write-insight-log
```

If something fails:

```bash
pod2wiki scan --config config/pod2wiki.config.yaml --retry-failed <run-id>
pod2wiki scan --config config/pod2wiki.config.yaml --resume <run-id>
pod2wiki replay <run-id> --config config/pod2wiki.config.yaml
```

If you want continuous monitoring:

```bash
pod2wiki watch --config config/pod2wiki.config.yaml --interval 4
```

## Operational advice

- Keep `max_videos_per_channel` conservative, usually around `3-5`
- Use `--dry-run` before expensive runs
- Prefer RSS over YouTube for large backfills
- Use local files for historical bulk imports
- If a feed already contains detailed show notes, Whisper may be unnecessary
- Use `retry-failed`, `resume`, and `replay` instead of restarting full batches

## Testing

Useful test commands:

```bash
pytest tests/test_web.py -q
pytest tests/test_persistence.py -q
```

On this repo, the web test suite currently provides the most stable end-to-end validation for the operator console.

## Summary

Use `pod2wiki` like this:

1. initialize config and env
2. verify with `doctor`
3. dry-run a scan
4. run real scans by CLI or Web UI
5. inspect outputs in `Preview`
6. recover with `resume`, `retry-failed`, or `replay`
7. automate recurring scans with `watch`

For most users, the shortest practical path is:

```bash
pod2wiki doctor
pod2wiki scan --config config/pod2wiki.config.yaml --days 1 --dry-run
pod2wiki ui
```
