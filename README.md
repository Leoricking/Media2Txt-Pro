🚀 Media2Txt Pro
繁體中文 | English

🇹🇼 繁體中文
影音轉結構化知識庫 —— 支援 YouTube 連結與本機多媒體檔案。

✨ 核心特色
🎬 全能轉錄：支援 YouTube 網址與本機影音 (MP4, MP3, WAV, WebM) 轉逐字稿。

📊 批次處理：支援多網址與多檔案同時加入任務佇列。

🧠 AI 智能摘要：串接 Ollama (Local LLM)，自動生成結構化內容總結。

🌐 多語系輸出：摘要可選 繁體中文 或 英文。

⚡ 效能優化：自動偵測 NVIDIA GPU 加速；若無則自動回退至 CPU。

🖥️ 直覺介面：專為桌面端設計的 GUI，無需程式背景即可上手。

⚙️ 環境安裝
Python: 建議使用 3.11 或 3.12。

依賴套件: pip install -r requirements.txt

關鍵組件:

Node.js: yt-dlp 運作必需。 下載

Ollama: 用於本地 AI 摘要。 下載

FFmpeg: 處理音訊分離。建議加入系統環境變數。

🧪 使用指南
YouTube: 貼入網址後點擊 [Start]。順序：手動字幕 > 自動字幕 > Whisper 辨識。

本地檔案: 點擊 [Add Local Media] 選取檔案。

混和模式: 可同時處理網址與本機檔案。

🇺🇸 English
Turn videos into structured knowledge — from YouTube or local media.

✨ Features
🎬 Universal Transcription: Supports YouTube URLs and local media (MP4, MP3, WAV, WebM).

📊 Batch Processing: Queue up multiple URLs and local files simultaneously.

🧠 AI Summarization: Integrated with Ollama (Local LLM) for structured content summaries.

🌐 Multilingual Output: Summary available in Traditional Chinese or English.

⚡ Hardware Acceleration: Auto-detects NVIDIA GPU; fallbacks to CPU if unavailable.

🖥️ Desktop GUI: User-friendly interface designed for non-technical users.

⚙️ Installation
Python: Version 3.11 or 3.12 is recommended.

Dependencies: pip install -r requirements.txt

Core Components:

Node.js: Required for yt-dlp runtime. Download

Ollama: For local AI summarization. Download

FFmpeg: Essential for media handling. Ensure it's in your PATH.

🧪 How to Use
YouTube: Paste URLs and click [Start]. Order: Manual Subs > Auto Subs > Whisper OCR.

Local Media: Click [Add Local Media] to select files.

Mixed Mode: Combine YouTube links and local files in a single run.

📂 專案結構 / Structure
Plaintext
media2txt/
├─ main.py            # Entry point
├─ requirements.txt   # Dependencies
├─ build.bat          # Build EXE script
├─ pipeline/          # Core logic (downloader, transcriber, summarizer)
└─ ui/                # UI components
🧾 輸出成果 / Output
Results are saved in the knowledge/ folder:

.txt: Transcript & AI Summary.

.vtt / .srt: Original subtitles (if available).

⚠️ 注意事項 / Notes
YouTube Error: Update yt-dlp via pip install -U yt-dlp.

Privacy: cookies.txt is ignored by git for security.

Ollama: Ensure you run ollama pull mistral (or your preferred model) before summarizing.