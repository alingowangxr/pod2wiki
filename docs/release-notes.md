# Release Notes

This release moves `pod2wiki` from a script-oriented tool into a more complete operating system for podcast and long-form content ingestion, review, and wiki publishing.

## Highlights

- Added a formal CLI entry point covering `scan`, `ui`, `watch`, `doctor`, `replay`, and related workflows.
- Added a FastAPI Web Console with Dashboard, Runs, Sources, Preview, Settings, and Users pages.
- Added multi-user login and session-based authentication.
- Added pre-run estimation for potential workload, LLM calls, Whisper usage, and risk warnings.
- Added SQLite-backed state persistence with resume, retry, replay, and run history support.
- Added a translation review workflow with side-by-side preview, review status, and notes.
- Added plugin-style post-processors and starter source packs.
- Added Web, integration, and recovery tests.
- Added formal usage documentation in [usage-guide.md](usage-guide.md).

## Major Changes

### CLI

- Added [src/pod2wiki/cli/main.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/cli/main.py:1)
- Expanded [src/pod2wiki/cli/fetch_podcasts.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/cli/fetch_podcasts.py:1)

### Web Console

- Added [src/pod2wiki/web/app.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/web/app.py:1)
- Added auth support in [src/pod2wiki/web/auth.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/web/auth.py:1)
- Added templates for dashboard, runs, sources, scan form, settings, preview, login, and user management

### Persistence and Recovery

- Added [src/pod2wiki/persistence/state.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/persistence/state.py:1)
- Added run tracking, status summaries, retry, replay, and review-state persistence

### Estimation and Post-processing

- Added [src/pod2wiki/reporting/estimator.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/reporting/estimator.py:1)
- Added [src/pod2wiki/processing/post.py](/C:/Users/szmik/pod2wiki/src/pod2wiki/processing/post.py:1)

### Documentation and Configuration

- Added [docs/usage-guide.md](/C:/Users/szmik/pod2wiki/docs/usage-guide.md:1)
- Added [config/pod2wiki.config.yaml](/C:/Users/szmik/pod2wiki/config/pod2wiki.config.yaml:1)
- Added [config/pod2wiki.env](/C:/Users/szmik/pod2wiki/config/pod2wiki.env:1)

## Repository Cleanup

- Moved core modules from `scripts/` into `src/pod2wiki/`
- Removed outdated docs: `CHANGELOG.md`, `CONTRIBUTING.md`, `REFACTOR.md`, `docs/repo-analysis.md`
- Updated `.gitignore` to exclude local test outputs and temporary artifacts

## Testing

- Added [tests/test_web.py](/C:/Users/szmik/pod2wiki/tests/test_web.py:1)
- Added [tests/test_integration.py](/C:/Users/szmik/pod2wiki/tests/test_integration.py:1)
- Added [tests/test_recovery.py](/C:/Users/szmik/pod2wiki/tests/test_recovery.py:1)

## Commit

- `0937ff3` `Add web console, recovery workflows, and usage docs`
