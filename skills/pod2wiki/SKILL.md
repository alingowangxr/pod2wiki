---
name: pod2wiki
description: Scan high-signal podcasts and long-form RSS feeds, summarize them, and write karpathy-claude-wiki compatible source-summary pages.
---

# pod2wiki Skill

Use this skill when the user says "scan podcasts", "刷播客", "刷一下播客", "podcast tracking", "播客追踪", "track podcasts this week", or asks to feed podcasts/blog RSS into a karpathy-style wiki.

## How pod2wiki is laid out after install

The one-click installer puts everything under the user's workspace:

```
<workspace>/
├── tools/pod2wiki/src/pod2wiki/     # Python package (collect / summarize / transcribe ...)
├── config/pod2wiki.config.yaml      # the one the user actually edits
├── config/pod2wiki.env              # contains LLM settings after the user fills the key
├── output/pod2wiki/                 # default local output if no wiki path
└── wiki/sources/                    # if user supplied a wiki, this points there
```

If the user invokes `/pod2wiki`, the slash command already has the right paths baked in — just run it.

## Steps for the natural-language path (no slash command)

1. Find `config/pod2wiki.config.yaml`. If missing, the user hasn't installed yet — point them at INSTALL-FOR-AI.md.
2. Run a dry-run first to confirm config parses:

```bash
python -m pod2wiki.cli.fetch_podcasts --config config/pod2wiki.config.yaml --env-file config/pod2wiki.env --days 1 --dry-run
```

3. Run the real scan with `--wiki-out` if the user has a wiki:

```bash
python -m pod2wiki.cli.fetch_podcasts \
  --config config/pod2wiki.config.yaml \
  --env-file config/pod2wiki.env \
  --output-dir output/pod2wiki \
  --wiki-out wiki/sources \
  --days 7 \
  --write-insight-log
```

When an RSS feed only ships a short `<description>` (Latent Space, many Substack
podcasts), the collector will automatically download the MP3 enclosure and run
faster-whisper (`tiny` model, first 600s by default) to recover the spoken
content. Override with `--whisper-model {tiny,base,small,medium,large-v3}`,
`--whisper-clip-seconds N` (use 0 for full episode), `--whisper-threshold N`
(auto-transcribe when description is shorter than N chars), or `--no-whisper`
to disable. Audio is cached in `output/pod2wiki/transcripts/`. If
`faster-whisper` is not installed, the run falls back to the RSS description
and emits a `[whisper] transcription unavailable` warning to stderr.

4. Parse stdout JSON and report to the user:

- `items_found`
- `source_pages_written`
- `raw_pages_written`
- `translation_pages_written`
- `insight_log`
- `verification_warnings`

## Architecture for developers

If the user is a developer asking about the code structure:

```
src/pod2wiki/
├── cli/fetch_podcasts.py      # Main orchestrator
├── collect/                   # RSS / YouTube / local file collectors
├── models.py                  # Pydantic schemas (SourceItem, StructuredSummary, Config)
├── errors.py                  # Exception hierarchy
├── persistence/file.py        # Markdown rendering + file I/O
├── reporting/insight_log.py   # Insight log generation
├── summarize/                 # LLM summarization + reversal detection
├── transcribe/whisper.py      # Whisper transcription
└── utils.py                   # Text/date/slug helpers
```

Key design principles:
1. All pipeline data flows through Pydantic models (not dicts)
2. Collect / Transcribe / Summarize / Render / Persist are separate modules
3. The new CLI (`python -m pod2wiki.cli.fetch_podcasts`) replaces the legacy `scripts/fetch_podcasts.py`

## Reversal Narrative Verification Rule

If `verification_warnings` is non-empty, do **not** reuse the flagged bullets in downstream research until the user has checked the raw transcript. These warnings catch LLM-added "X rather than Y" framings that often hallucinate the reversal.
