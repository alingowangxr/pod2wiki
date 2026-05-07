# Contributing

## Basic Rules

- Keep each PR small and easy to review.
- Preserve the zero-code / AI-agent install path; do not require users to become Python package maintainers.
- Do not commit real transcripts, generated output, `.env` files, API keys, or private wiki content.
- Before publishing or opening a PR, run:

```bash
python -m pytest tests/ -v
python -m pod2wiki.cli.fetch_podcasts --config examples/config.ai-investing.yaml --days 1 --dry-run
```

CI runs the same public-repo preflight and smoke checks.

## Architecture (after refactor)

The project is now structured as a proper Python package under `src/pod2wiki/`:

```
src/pod2wiki/
├── cli/fetch_podcasts.py      # Main orchestrator (replaces scripts/fetch_podcasts.py)
├── collect/                   # RSS, YouTube, and file collectors
├── models.py                  # Pydantic schemas (SourceItem, StructuredSummary, Config, ...)
├── errors.py                  # Custom exception hierarchy
├── persistence/file.py        # Markdown rendering + file I/O
├── reporting/insight_log.py   # Insight log generation
├── summarize/                 # LLM summarization + reversal detection
├── transcribe/whisper.py      # Whisper transcription service
├── utils.py                   # Text/date/slug helpers
└── proxy.py                   # Proxy configuration
```

Legacy scripts in `scripts/` are kept for backward compatibility but will be deprecated in the next release.

### Design Principles

1. **Data models**: All pipeline data flows through `pod2wiki.models` (Pydantic), not `dict[str, Any]`.
2. **Separation of concerns**: Collect / Transcribe / Summarize / Render / Persist are separate modules.
3. **Testability**: New code should come with unit tests under `tests/`.
4. **Backward compatibility**: The new CLI (`python -m pod2wiki.cli.fetch_podcasts`) accepts the same arguments as the old script.
