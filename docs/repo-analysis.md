# pod2wiki Repo Analysis

本文件整理此 repo 的功能定位、執行流程、設定結構、工程架構與重構建議，作為後續維護與設計討論的長期參考。

## 1. Repo 定位

`pod2wiki` 是一個研究資料攝取工具，目的是把播客、YouTube 字幕、長文 RSS、以及本地 transcript 轉成 markdown-first 的知識庫素材，並輸出為 `karpathy-claude-wiki` 相容的 `source-summary` 頁面。

它不是 Web app，也不是 API server，而是一組以 Python CLI 為核心的批次處理腳本。主入口在 `scripts/fetch_podcasts.py`，專案定義在 `pyproject.toml`。

從產品面看，它是個人研究 wiki 的 ingestion pipeline。

從工程面看，它是以單一大型 orchestrator 腳本為核心的 markdown ETL 工具。

從使用面看，它真正的價值不是單次摘要，而是把原文、摘要、翻譯、假設鏈接與研究紀錄落成可持續保存的本地知識資產。

## 2. 主要功能

### 2.1 多來源收集

主流程支援三類來源：

- RSS / blog feed
- YouTube 頻道、搜尋詞、指定 URL
- 本地 markdown / text transcript

相關函式：

- `rss_items`
- `collect_rss`
- `collect_youtube`
- `collect`
- `file_item`

### 2.2 自動補 transcript

對 RSS podcast，如果 `<description>` 過短但有音訊 enclosure，系統會：

1. 下載音訊
2. 視設定裁剪前 N 秒
3. 用 `faster-whisper` 轉錄
4. 用轉錄結果覆蓋原始 `raw_text`

相關函式：

- `_download_audio`
- `_clip_audio`
- `maybe_transcribe`
- `podcast_rss_transcribe.transcribe_audio`

### 2.3 LLM 結構化摘要

每篇內容會被送進 LLM 產生固定 JSON 結果，欄位包含：

- `summary`
- `core_views`
- `key_data`
- `related_tickers`
- `related_concepts`
- `predictions`
- `h_links`
- `speakers`
- `key_quotes`

不是產出自由文字，而是產出下游可消費的結構化結果。

### 2.4 多種輸出資產

每筆內容至少會寫出：

- `raw/podcasts/` 下的原文存檔
- `sources/` 下的 `source-summary`

可選地再加：

- `translations/` 下的全文翻譯
- 本輪掃描的 `insight log`

### 2.5 研究工作流附加功能

- `seen_history.json`：避免重複處理
- `verification_warnings`：標記可能帶有敘事反轉幻覺的摘要句
- insight log：把本次掃描整合成投研日志
- no-LLM fallback：沒有 API key 時仍可做低信任抽取式輸出

## 3. 架構總覽

整體架構屬於「單一 orchestrator + 多個輔助模組」。

### 3.1 核心模組

#### `scripts/fetch_podcasts.py`

整個系統的主 orchestrator，負責：

- CLI 參數解析
- config / env 載入
- RSS / YouTube / file 收集
- Whisper 轉錄補全
- LLM 摘要與翻譯
- markdown 輸出
- history 更新
- insight log 產生

#### `scripts/llm_client.py`

輕量 OpenAI-compatible LLM client，負責：

- provider 設定解析
- `.env` 載入
- chat/completions 呼叫
- JSON 回覆抽取

支援：

- DeepSeek
- Kimi
- GLM
- Qwen
- OpenAI

#### `scripts/podcast_rss_transcribe.py`

處理：

- 音訊下載
- `ffprobe` 時長探測
- `faster-whisper` 轉錄
- raw transcript markdown 輸出

#### `scripts/podcast_batch_summarize.py`

獨立的 transcript 批次摘要工具，另包含：

- `detect_reversal_flags`

用途是對既有 transcript 批次生成 JSON 摘要，並做敘事反轉風險提示。

#### `scripts/proxy_config.py`

代理設定封裝，支援：

- 明確指定 `PODCAST_PROXY`
- 自動探測本地 socks5 port
- 提供 `requests` 可直接使用的 proxy dict

#### `scripts/podcast_feed_registry.py`

內建公開 podcast feed registry，並支援 iTunes lookup fallback。

#### `scripts/preflight_public_repo.py`

公開發佈前自檢工具，用來阻擋：

- 真實或疑似 secret
- 本機痕跡
- 私有輸出資料
- 使用者資料路徑

### 3.2 分層理解

如果用分層看，系統大致可拆成：

1. Input layer
   RSS / YouTube / local transcript
2. Enrichment layer
   HTML 清洗、字幕抓取、Whisper transcript
3. Intelligence layer
   LLM summary、translation、verification warning
4. Persistence layer
   markdown raw/source/translation + history
5. Installer / agent layer
   install scripts、skill、slash command

## 4. 執行資料流

資料流大致如下：

1. 讀取 YAML config 與 env
2. 根據 mode 收集 RSS / YouTube / local file
3. 對 RSS podcast 視需要補跑 Whisper
4. 統一整理成 item dict
5. 對每個 item 呼叫摘要流程
6. 產出 raw transcript markdown
7. 產出 source-summary markdown
8. 視需要產出全文翻譯
9. 更新 `seen_history.json`
10. 視需要產生 insight log

系統最重要的內部統一技巧是：不管來源是哪裡，後半段都吃同一種 `item` dict schema。

## 5. `fetch_podcasts.py` 逐段 walkthrough

### 5.1 基礎工具函式

檔案前段包含：

- `slugify`
- `strip_html`
- `strip_markdown_light`
- `parse_date`
- `parse_youtube_date`
- `is_recent_youtube`
- `youtube_video_id`
- `run_ytdlp`
- `parse_ytdlp_json_lines`

這些函式的作用是把外部來源整理成統一的內部資料格式。

### 5.2 YouTube transcript 子流程

主要函式：

- `parse_vtt`
- `transcript_via_api`
- `transcript_via_ytdlp`
- `fetch_youtube_transcript`

設計上有雙重 fallback：

1. 先試 `youtube-transcript-api`
2. 失敗後退回 `yt-dlp`
3. 都失敗就略過影片

### 5.3 History 與 Whisper 設定

- `load_history`
- `save_history`
- `_whisper_settings`

這一段負責執行期狀態與 config default merge。

### 5.4 RSS podcast 自動轉錄

關鍵函式：

- `_download_audio`
- `_clip_audio`
- `maybe_transcribe`

啟動條件是：

- item 有 `audio_url`
- Whisper enabled
- `raw_text` 長度小於 `auto_threshold`

這是成本控制邏輯：如果 RSS 已有長篇 description，就不額外下載音訊跑 ASR。

### 5.5 RSS 收集

`rss_items` 會：

1. 抓 feed XML
2. 解析 item
3. 過濾日期
4. 擷取 `title/link/guid/description/enclosure`
5. 組成統一 item dict
6. 視條件補 transcript

### 5.6 來源規劃與收集

- `planned_inputs`
- `collect_rss`
- `collect_youtube`
- `collect`

`collect_youtube` 邏輯最重，因為同時處理：

- 頻道掃描
- 搜尋詞掃描
- 指定 URL
- recent filter
- history dedupe
- transcript backend 選擇

### 5.7 本地檔案匯入

`file_item` 直接把本地 markdown / text transcript 包成統一 item dict，使系統可吃離線資料。

### 5.8 no-LLM fallback

`summarize_without_llm` 會：

- 抽取首段作 summary
- 粗略抽 keyword
- 用 keyword 對 hypotheses 做低精度匹配
- 生成 `confidence: low` 的 fallback 結果

這主要是給 smoke test、無 API key、或降低成本時使用。

### 5.9 正式摘要流程

`summarize_item` 是主智能節點，會：

1. 截斷過長 transcript
2. 注入 hypotheses
3. 要求模型輸出 strict JSON
4. 呼叫 `llm_client.chat`
5. 用 `extract_json` 解析
6. 用 `detect_reversal_flags` 再檢查輸出風險

### 5.10 全文翻譯

`translate_full_text` 的策略是：

1. 先 `split_text`
2. 分 chunk 翻譯
3. 保留名字、公司、ticker、數字、URL、單位
4. 最後拼接全文

### 5.11 輸出層

主要函式：

- `write_raw`
- `write_translation`
- `write_source`

其中 `write_source` 最重要，因為它會把摘要轉成 wiki-friendly 的 `source-summary` 格式，包含：

- TL;DR
- Key Data
- Direct Quotes
- Implications
- Verifiable Predictions
- Hypothesis Links
- Verification Warnings

### 5.12 Insight log 層

- `item_log_block`
- `fallback_report`
- `generate_insight_report`
- `append_insight_log`

這一層把多篇結構化輸出再整理成一份可閱讀的投研日志。

### 5.13 主程式 `main`

`main` 負責：

1. 解析 CLI 參數
2. 載入 config / env
3. 決定 days、limits、whisper 設定
4. dry-run 或實際 collect
5. 摘要每個 item
6. 寫 raw/source/translation
7. 更新 history
8. 產 insight log
9. 輸出 JSON payload

## 6. Config schema 詳解

範例設定在 `examples/config.ai-investing.yaml`。

### 6.1 基本欄位

#### `theme`

主要是主題標籤，影響整體語境與 insight log 識別，不直接決定抓取邏輯。

#### `days_lookback`

預設掃描時間窗口。可被 CLI `--days` 或 `--days-quick` 覆蓋。

#### `max_items_per_feed`

每個 RSS / blog feed 的單源上限，不是整次執行的全域上限。

#### `max_videos_per_channel`

每個 YouTube channel 或 search query 的候選上限。

#### `max_transcript_chars`

送給摘要模型前允許保留的最大字元數；超過就做頭尾截斷。

### 6.2 `whisper`

包含：

- `enabled`
- `model`
- `clip_seconds`
- `auto_threshold`

用途是控制 RSS 音訊補 transcript 的成本、速度與範圍。

### 6.3 `llm`

包含：

- `provider`
- `model`
- `max_tokens`
- `translation_max_tokens`
- `report_max_tokens`

這一塊控制摘要、全文翻譯、insight log 使用的模型與輸出上限。

### 6.4 `channels`

每個 channel item 通常可同時包含：

- `name`
- `youtube`
- `rss`
- `keywords`

這代表同一來源可走 YouTube 與 RSS 雙軌收集。

### 6.5 `people_searches` / `exec_searches`

兩者本質上都只是 YouTube 搜尋字串陣列。程式對兩者沒有行為差異，分類純粹是為了讓配置更容易讀。

### 6.6 `youtube_urls`

顯式指定特定 YouTube 影片，適合補抓單集。

### 6.7 `blog_feeds`

純文字 RSS 來源，適合 blog / article 類型內容。

### 6.8 `hypotheses`

這是研究工作流的核心配置。每個 hypothesis 包含：

- `title`
- `keywords`

用途是：

- 摘要時讓模型輸出 `h_links`
- no-LLM 模式下用 keyword 粗略對應

它的本質是把內容攝取流程接到使用者自己的研究框架。

### 6.9 `reversal_triggers`

定義哪些詞會觸發敘事反轉警告，例如：

- `而非`
- `实际上`
- `rather than`
- `instead of`

這些設定會交給 `detect_reversal_flags` 使用。

## 7. 安裝與 agent 整合

此 repo 不只提供 runtime，也包含安裝器與 agent 整合。

### 7.1 安裝腳本

- `scripts/install.ps1`
- `scripts/install.sh`

安裝器會：

- 複製工具到 workspace
- 生成 `config/pod2wiki.config.yaml`
- 生成 `config/pod2wiki.env`
- 生成 Claude slash command `/pod2wiki`
- 安裝 `skills/pod2wiki/SKILL.md`
- 安裝 Python 依賴
- 跑 dry-run smoke test

### 7.2 skill

`skills/pod2wiki/SKILL.md` 定義了給 agent 使用的操作協議，包含：

- 如何找 config
- 先跑 dry-run
- 再跑正式掃描
- 如何回報 `items_found`、`source_pages_written`、`raw_pages_written` 等結果

## 8. 工程優點

- 產品定位明確
- markdown-first，資料可攜性高
- LLM provider abstraction 足夠薄
- 有 no-LLM fallback
- 有 verification warning，知道投研場景的風險點
- 有 public repo preflight，對 repo hygiene 有明確意識
- 安裝器與 agent workflow 有整合思路

## 9. 限制與風險

### 9.1 單檔過胖

`fetch_podcasts.py` 超過 1100 行，主流程、I/O、prompt、render、寫檔全部混在一起，維護成本偏高。

### 9.2 缺少正式資料模型

目前主要靠 `dict[str, Any]` 當內部資料結構，缺少明確型別與 schema，容易造成：

- 欄位拼錯
- 某來源漏欄位
- runtime 才出錯
- 測試難寫

### 9.3 測試覆蓋偏薄

目前主要測試集中在 `preflight_public_repo.py`，缺少主流程與輸出格式測試。

### 9.4 對外部依賴敏感

YouTube、`yt-dlp`、字幕 availability、proxy、LLM API 都是外部依賴，穩定性會受外部環境影響。

### 9.5 JSON schema 驗證不足

雖然要求模型輸出 strict JSON，但目前只做寬鬆抽取，沒有真正 schema validation。

### 9.6 RSS parser 與錯誤分類較輕量

目前用 `xml.etree.ElementTree` 與多處 `except Exception`，可用但不是強韌型設計。

## 10. 重構建議與技術債清單

### 10.1 最高優先級

#### A. 拆分 `fetch_podcasts.py`

建議拆成：

- `domain/models.py`
- `ingest/rss.py`
- `ingest/youtube.py`
- `transcribe/whisper.py`
- `summarize/service.py`
- `render/markdown.py`
- `reporting/insight_log.py`
- `cli/fetch_podcasts.py`

#### B. 引入正式資料模型

至少定義：

- `SourceItem`
- `StructuredSummary`
- `VerificationWarning`
- `RunResult`

可用 `dataclass` 或 `pydantic`。

#### C. 增加 LLM 輸出 schema validation

建議：

- 定義 summary JSON schema
- parse 後立刻 validate
- 不合法輸出要有明確錯誤型別

### 10.2 中優先級

#### D. 抽 prompt

把 prompt 與業務流程分離，例如：

- `prompts/source_summary.py`
- `prompts/translation.py`
- `prompts/insight_log.py`

#### E. 抽 collector interface

讓不同來源有更明確的 adapter contract，方便未來擴充更多來源。

#### F. 分離 render 與 persistence

例如：

- `render_source_markdown(summary) -> str`
- `write_text(path, content)`

這樣較容易做 snapshot test。

### 10.3 低到中優先級

#### G. 對 config 做正式驗證

目前 `load_config` 只確認 YAML 頂層是 dict，不夠。

#### H. 提升 `keywords` 配置的實際利用率

現在 `channels[].keywords` 幾乎沒有被真正用於排序、篩選或摘要提示。

#### I. 補測試

優先補：

- `rss_items`
- `parse_vtt`
- `split_text`
- `summarize_without_llm`
- `write_source`
- `detect_reversal_flags`
- `extract_json`
- `main --dry-run`

#### J. 細化錯誤分類

可考慮定義：

- `FeedFetchError`
- `TranscriptUnavailableError`
- `LLMResponseError`
- `OutputWriteError`

## 11. 建議的重構順序

1. 先補測試，保住既有行為
2. 再引入資料模型
3. 再拆 render 與 collectors
4. 最後才拆主 orchestrator

這樣風險最低，也比較不容易在重構時破壞既有使用流程。

## 12. 驗證備註

在本次分析過程中有執行 `pytest -q`。測試失敗，但從輸出看，主要原因是當前執行環境對暫存目錄與 pytest cache 的寫入權限有限，屬於環境層級問題，不能直接據此判定 repo 的邏輯失敗。

## 13. 一句話總結

這個 repo 的方向與產品形態是清楚的：它不是做「播客播放器」，而是在做「研究知識庫的輸入管線」。目前最大的技術債不是功能不足，而是成功長大後仍維持單檔腳本形態；若要長期維護，應優先補齊測試、資料模型與模組邊界。
