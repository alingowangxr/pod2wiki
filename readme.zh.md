# pod2wiki

[![Latest Release](https://img.shields.io/github/v/release/alingowangxr/pod2wiki?display_name=tag)](https://github.com/alingowangxr/pod2wiki/releases/latest)
[![Podcast Lint](https://github.com/alingowangxr/pod2wiki/actions/workflows/podcast-lint.yml/badge.svg)](https://github.com/alingowangxr/pod2wiki/actions/workflows/podcast-lint.yml)

> **30 秒看懂**：把高品質播客（YouTube/RSS）和長文 RSS 自動轉成中文摘要 + 英文原文存檔，寫進 [karpathy-claude-wiki](https://github.com/alingowangxr/karpathy-claude-wiki)。

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

## 關於 pod2wiki

pod2wiki 是一個面向 LLM 知識庫的 Podcast / RSS ingestion engine，專為將 YouTube 影片、播客與長文 RSS 轉化為 LLM 友好的 `source-summary` 頁面而設計。它不僅是 `karpathy-claude-wiki` 的理想輸入端，也是建立個人 AI 投研知識庫的核心組件。

> **專案起源**：本倉庫是基於 [Benboerba620/pod2wiki](https://github.com/Benboerba620/pod2wiki) 重新建構，並加入 CLI 與 Web UI 的擴展版本。

## 核心特性

- **極致效能**：全鏈路 `asyncio` 異步並發，抓取與處理速度提升 3-5 倍。
- **專業控制台**：內建 FastAPI 網頁介面，支援即時進度監控、預算預估與多用戶管理。
- **智慧摘要**：支援 DeepSeek、Gemini、OpenAI 及本地 Ollama (Gemma)，針對投資與技術領域優化。
- **穩定可靠**：基於 SQLite 的狀態管理，支援斷點續傳與失敗重試。
- **精準轉錄**：整合 `faster-whisper`，支援自動偵測語音內容並按需轉錄。

## 快速開始

### 推薦：AI Agent 一鍵安裝
複製以下指令給 Claude Code、Cursor 或任何 AI Agent：
> 幫我按這個協議安裝 pod2wiki：https://github.com/alingowangxr/pod2wiki/blob/main/INSTALL-FOR-AI.md

### 手動安裝
```bash
# 1. 克隆與安裝
git clone https://github.com/alingowangxr/pod2wiki.git
cd pod2wiki
pip install -e .

# 2. 初始化工作區
pod2wiki init --target .

# 3. 環境診斷（需在 config/pod2wiki.env 填入 API Key）
pod2wiki doctor
```

## 專案架構

```
src/pod2wiki/
├── cli/main.py           # Typer CLI 統一入口
├── web/                  # FastAPI Web Console
├── collect/              # RSS / YouTube / Local File 收集器
├── transcribe/           # Whisper 語音轉錄
├── summarize/            # LLM 摘要與翻譯
├── processing/           # 後處理 Plugin Hook
├── persistence/          # Markdown 寫入 + SQLite 狀態追蹤
├── reporting/            # Token / Cost 預估 + 洞察日誌
└── llm_client.py         # Async LLM Client
```

## 常用工作流

- **啟動網頁控制台（推薦）**：
  ```bash
  pod2wiki ui
  ```
  訪問 `http://127.0.0.1:8080` 進行視覺化管理。

- **命令行掃描**：
  ```bash
  pod2wiki scan --config config/pod2wiki.config.yaml --days 7 --write-insight-log
  ```

- **定時監控**：
  ```bash
  pod2wiki watch --interval 4
  ```

- **回放歷史 Run**：
  ```bash
  pod2wiki replay <run-id>
  ```

## 文檔
- [docs/usage-guide.md](docs/usage-guide.md): 完整使用手冊（配置、命令詳解、故障排除）。
- [INSTALL-FOR-AI.md](INSTALL-FOR-AI.md): 給 AI Agent 的安裝協議。

## License
MIT.
