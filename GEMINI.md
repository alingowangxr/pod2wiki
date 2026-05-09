# Project Instructions: pod2wiki

## Project Overview
**pod2wiki** is a high-concurrency, async-first tool designed to turn high-signal podcasts (YouTube/RSS) and long-form RSS feeds into Chinese summaries and archived English transcripts. It is optimized for ingestion into personal LLM knowledge bases (specifically `karpathy-claude-wiki`).

### Key Technologies
- **Language:** Python 3.10+
- **Frameworks:** FastAPI (Web Console), Typer (CLI), Pydantic (Models)
- **Concurrency:** `asyncio`, `httpx`
- **Processing:** `yt-dlp` (YouTube), `faster-whisper` (Transcription), LLM (Gemini, DeepSeek, Ollama, etc.)
- **Persistence:** SQLite (State tracking), Markdown (Output)
- **UI:** Vanilla CSS + Jinja2 (Web Console)

### Architecture
- `src/pod2wiki/cli/`: Typer-based CLI entry points and orchestration logic.
- `src/pod2wiki/web/`: FastAPI web server and templates for the local console.
- `src/pod2wiki/collect/`: Collectors for RSS feeds and YouTube videos.
- `src/pod2wiki/summarize/`: LLM client and summarization logic.
- `src/pod2wiki/transcribe/`: Whisper-based audio transcription.
- `src/pod2wiki/persistence/`: SQLite state management and file-based persistence.
- `src/pod2wiki/reporting/`: Cost estimation and insight logging.

---

## Building and Running

### Prerequisites
- Python 3.10+
- `ffmpeg` and `yt-dlp` installed in the system PATH.

### Installation
```bash
pip install -e .
# Or with transcription support
pip install -e .[transcribe]
```

### Key Commands
- **Diagnostic:** `pod2wiki doctor` (Checks dependencies, API keys, and environment).
- **Initialize:** `pod2wiki init` (Sets up config templates and wiki structure).
- **Web Console:** `pod2wiki ui` (Starts the web interface at http://127.0.0.1:8080).
- **Scan:** `pod2wiki scan --config config/pod2wiki.config.yaml --days 7` (Processes new content).
- **Watch:** `pod2wiki watch --config config/pod2wiki.config.yaml --interval 4` (Scheduled background scanning).
- **Test Feed:** `pod2wiki test-feed <URL>` (Validates a single source).

---

## Development Conventions

### Coding Style
- Follow **PEP 8**.
- Use **Type Hints** for all function signatures and class members.
- Use **Async/Await** for I/O bound operations (HTTP requests, file I/O).
- Linting and Formatting: Use `ruff` (configured in `pyproject.toml`).

### Testing
- **Framework:** `pytest` with `pytest-asyncio`.
- **Location:** All tests are in the `tests/` directory.
- **Run Tests:** `pytest`
- **Standard:** Always add integration tests for new collectors or processing logic. Use `test_web.py` as a reference for end-to-end console validation.

### Configuration Management
- **Runtime Config:** Stored in YAML (e.g., `config/pod2wiki.config.yaml`).
- **Secrets & Environment:** Managed via `.env` files (e.g., `config/pod2wiki.env`). Never commit API keys.
- **State Tracking:** `pod2wiki_v1.db` (SQLite) handles run history, resume/retry logic, and user authentication.

### UI Development
- The Web Console uses **FastAPI + Jinja2 + HTMX** (for dynamic fragments like status updates).
- **Styling:** Prefer Vanilla CSS. Keep the interface clean and responsive.
- **Templates:** Located in `src/pod2wiki/web/templates/`.

---

## Operational Guidelines
- **Surgical Edits:** When modifying CLI commands, ensure compatibility with both the orchestrator (`fetch_podcasts.py`) and the Web UI.
- **Error Handling:** Use custom exceptions defined in `src/pod2wiki/errors.py`.
- **Validation:** Always run `pod2wiki doctor` and a `scan --dry-run` after significant architectural changes.
