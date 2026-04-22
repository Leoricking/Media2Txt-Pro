# 🚀 Media2Txt Pro

[**繁體中文**](#-繁體中文) | [**English**](#-english)

---

## 🇹🇼 繁體中文

> **影音轉結構化知識庫** —— 一鍵將 YouTube 影片或本機影音轉化為精確的逐字稿與 AI 摘要。

### ✨ 核心特色
* **🎬 全能轉錄**：支援 YouTube 網址與本機多媒體檔案 (MP4, MP3, WAV, WebM)。
* **📊 批次任務**：支援多個網址與檔案同時處理，自動排隊執行。
* **🧠 AI 智能摘要**：整合 **Ollama** 本地大模型，自動生成結構化的內容總結。
* **🌐 多語系支援**：摘要可自由選擇 **繁體中文** 或 英文輸出。
* **⚡ 效能優化**：支援 NVIDIA GPU 加速 (CUDA)，大幅提升轉錄速度。
* **🖥️ 直覺介面**：專為桌面端設計的 GUI，無需程式背景即可上手。

### ⚙️ 環境準備 (必需組件)
1. **Python 3.11+**: [官方下載](https://www.python.org/downloads/)
2. **Ollama (AI 摘要)**: [官方下載](https://ollama.com/) (安裝後請執行 `ollama pull mistral`)
3. **Node.js**: [官方 LTS 版本](https://nodejs.org/) (yt-dlp 運作必需)
4. **FFmpeg**: [官方下載](https://ffmpeg.org/download.html) (請確保將 `bin` 路徑加入環境變數)

### 🚀 快速開始
```bash
# 安裝依賴套件
pip install -r requirements.txt

# 啟動程式
python main.py

🇺🇸 English
Media to Structured Knowledge — Effortlessly transform YouTube videos or local media into precise transcripts and AI-powered summaries.

✨ Key Features
🎬 Universal Transcription: Supports YouTube URLs and local files (MP4, MP3, WAV, WebM).

📊 Batch Queuing: Process multiple URLs and files in a single automated session.

🧠 AI Summarization: Built-in Ollama integration for local, private AI content analysis.

🌐 Multilingual Output: Choose between Traditional Chinese or English for your summaries.

⚡ Hardware Acceleration: Full NVIDIA GPU (CUDA) support for lightning-fast processing.

🖥️ User-Friendly GUI: Clean desktop interface designed for everyone.

⚙️ Prerequisites
Please install the following components before running the application:

Python 3.11+: Official Download

Ollama (AI Summary): Official Download (Run ollama pull mistral after install)

Node.js: Official LTS Release (Required for yt-dlp)

FFmpeg: Download Builds (Ensure bin folder is added to your PATH)

🚀 Quick Start
# Install dependencies
pip install -r requirements.txt

# Run application
python main.py

📂 專案結構 / Structure
Plaintext
media2txt/
├─ main.py            # 程式啟動入口 / Entry point
├─ requirements.txt   # 依賴清單 / Dependencies
├─ build.bat          # 一鍵封裝 EXE / Build script
├─ pipeline/          # 核心邏輯 / Core processing logic
│  ├─ downloader.py   # 影音下載 / Media Downloader
│  ├─ transcriber.py  # 語音轉文字 / Whisper Transcriber
│  └─ summarizer.py   # AI 摘要 / LLM Summarizer
└─ ui/                # 介面組件 / UI components
   └─ main_window.py  # 主視窗邏輯 / Main GUI logic
🧾 輸出成果 / Output
處理完成後，結果將自動儲存於 knowledge/ 資料夾：

.txt: 包含逐字稿與結構化 AI 摘要 / Contains transcript and structured AI summary.

.vtt / .srt: 原始字幕檔案 / Original subtitle files.

⚠️ 注意事項 / Notes
YouTube 下載: 若遇到下載失敗，請執行 python -m pip install -U yt-dlp 更新下載核心。

YouTube Extraction: If extraction fails, run python -m pip install -U yt-dlp to update.

隱私安全性: 本專案自動忽略 cookies.txt，確保您的個人憑證不會上傳。

Security: cookies.txt is automatically ignored to ensure your credentials are never uploaded.
