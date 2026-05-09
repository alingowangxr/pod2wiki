[English](readme.md) | [中文](readme.zh.md)

[![Latest Release](https://img.shields.io/github/v/release/alingowangxr/pod2wiki?display_name=tag)](https://github.com/alingowangxr/pod2wiki/releases/latest)
[![Podcast Lint](https://github.com/alingowangxr/pod2wiki/actions/workflows/podcast-lint.yml/badge.svg)](https://github.com/alingowangxr/pod2wiki/actions/workflows/podcast-lint.yml)

> **In 30 seconds**：Turn high-signal podcasts (YouTube/RSS) and long-form RSS into Chinese summaries plus archived English transcripts, written into your personal LLM wiki.

```mermaid
flowchart LR
    A[YouTube / Podcast / RSS] --> B[pod2wiki]
    B --> C[Whisper Transcription]
    C --> D[LLM Summarization]
    D --> E[source-summary Markdown]
    E --> F[karpathy-claude-wiki]
    F --> G[daily-watchlist]
    G --> H[Hypothesis Tracking]
    H --> F
    style B fill:#c7d2fe,stroke:#3730a3,color:#000
    style F fill:#d1fae5,stroke:#047857,color:#000
```

## About pod2wiki

pod2wiki is an ingestion engine for LLM knowledgebases, turning podcasts, YouTube videos, and long-form RSS feeds into `source-summary` pages compatible with `karpathy-claude-wiki`. It serves as the primary data entry layer for your personal AI research wiki.

> **Project Origin**: This repository is rebuilt based on [Benboerba620/pod2wiki](https://github.com/Benboerba620/pod2wiki), extending it with a CLI and Web UI.

## Key Features

- **High Concurrency**: Async-first engine built on `asyncio` and `httpx`, delivering 3-5x faster processing.
- **Web Console**: Professional FastAPI-based UI for monitoring, cost estimation, and multi-user auth.
- **Smart Summarization**: Native support for DeepSeek, Gemini, OpenAI, and Ollama (Gemma).
- **Robust Recovery**: SQLite-backed state tracking with `--resume`, `--retry-failed`, and `--replay` capabilities.
- **Transcription**: Integrated `faster-whisper` for high-quality audio-to-text conversion.

## Quick Start

### Recommended: One-click AI Install
Paste this instruction into Claude Code, Cursor, or any AI Agent:
> Install pod2wiki for me using this protocol: https://github.com/alingowangxr/pod2wiki/blob/main/INSTALL-FOR-AI.md

### Manual Installation
```bash
# 1. Clone and Install
git clone https://github.com/alingowangxr/pod2wiki.git
cd pod2wiki
pip install -e .

# 2. Initialize Workspace
pod2wiki init --target .

# 3. Diagnostic (Requires API Key in config/pod2wiki.env)
pod2wiki doctor
```

## Project Structure

```
src/pod2wiki/
├── cli/main.py           # Typer CLI entrypoint
├── web/                  # FastAPI Web Console
├── collect/              # RSS / YouTube / Local File collectors
├── transcribe/           # Whisper transcription
├── summarize/            # LLM summarization & translation
├── processing/           # Post-processing plugin hooks
├── persistence/          # Markdown writer + SQLite state tracking
├── reporting/            # Token/Cost estimator + Insight log
└── llm_client.py         # Async LLM client
```

## Common Workflows

- **Launch Web Console**:
  ```bash
  pod2wiki ui
  ```
  Open `http://127.0.0.1:8080` for a visual management experience.

- **CLI Scan**:
  ```bash
  pod2wiki scan --config config/pod2wiki.config.yaml --days 7 --write-insight-log
  ```

- **Watch Mode**:
  ```bash
  pod2wiki watch --interval 4
  ```

- **Replay Historical Run**:
  ```bash
  pod2wiki replay <run-id>
  ```

## Documentation
- [docs/usage-guide.md](docs/usage-guide.md): Full operating guide (Configuration, CLI details, Recovery).
- [INSTALL-FOR-AI.md](INSTALL-FOR-AI.md): Installation protocol for AI agents.

## License
MIT.
