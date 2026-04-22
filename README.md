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
