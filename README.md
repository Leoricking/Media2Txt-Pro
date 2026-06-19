# Media2Txt Pro Community

> 將 YouTube 影片與本機影音檔案轉成逐字稿、AI 摘要與可搜尋知識檔案的 Windows 桌面工具。
> Transcribe YouTube videos and local media into transcripts, AI summaries, and reusable knowledge files.

---

## 目錄

- [程式用途](#程式用途)
- [主要特色](#主要特色)
- [適合使用情境](#適合使用情境)
- [系統需求](#系統需求)
- [安裝方式](#安裝方式)
- [Whisper 模型設定](#whisper-模型設定)
- [Ollama 摘要模型設定](#ollama-摘要模型設定)
- [啟動方式](#啟動方式)
- [完整使用流程](#完整使用流程)
- [執行模式說明](#執行模式說明)
- [輸出內容與目錄](#輸出內容與目錄)
- [轉錄處理流程](#轉錄處理流程)
- [GPU 原生閃退保護](#gpu-原生閃退保護)
- [Chunk Recovery 切段救援](#chunk-recovery-切段救援)
- [摘要處理方式](#摘要處理方式)
- [支援格式](#支援格式)
- [環境變數](#環境變數)
- [常見問題](#常見問題)
- [專案結構](#專案結構)
- [Git 建議](#git-建議)
- [安全與使用限制](#安全與使用限制)

---

## 程式用途

Media2Txt Pro Community 是一套本機桌面影音轉文字工具，主要用途如下：

1. 將 YouTube 影片轉成逐字稿。
2. 將本機影片或音訊檔轉成逐字稿。
3. 優先使用影片現有字幕，沒有字幕時才使用 Whisper 語音辨識。
4. 使用本機 Ollama 模型產生繁體中文或英文摘要。
5. 將結果保存到 `knowledge/`，建立可長期整理與搜尋的個人知識庫。
6. 支援多筆 YouTube 網址及多個本機檔案批次處理。
7. 避免單支影片失敗時中斷整批任務。
8. 隔離 CUDA / CTranslate2 原生崩潰，降低整個 GUI 被一起關閉的風險。
9. 對特殊或損壞音訊提供正規化與切段救援流程。

所有核心處理都可以在本機完成。Whisper 模型與 Ollama 模型不需要把逐字稿傳送到第三方雲端服務。

---

## 主要特色

### YouTube 與本機影音

- 支援單一或多個 YouTube URL。
- 支援多個本機影片、音訊檔案。
- YouTube 與本機檔案可以混合排入同一批任務。
- YouTube 字幕失敗時可降級為僅下載音訊，再交由 Whisper 處理。
- 可自動偵測 JDownloader 2 內附的 FFmpeg。

### 逐字稿

- 優先使用 YouTube 手動字幕。
- 沒有手動字幕時嘗試自動字幕。
- 沒有可用字幕時使用 faster-whisper。
- 支援 NVIDIA CUDA GPU。
- 支援 CPU `int8` fallback。
- 支援繁體中文轉換及常見辨識錯字清理。
- 支援長影片低負載策略。
- 支援 Chunk Recovery 切段救援。

### AI 摘要

- 使用本機 Ollama。
- 摘要語言可選：
  - 繁體中文
  - English
- 依內容自動判斷領域：
  - 股票／市場解盤
  - 投資理財教育
  - 心理學／自我成長
  - 科技
  - 商業
  - 醫療
  - 科學
  - 法律
  - 教學
  - 一般內容
- 長逐字稿會自動分段摘要，再合併成完整摘要。
- 會保留重要數字、條件、價位、風險與操作邏輯。
- 會清理重複句、片尾宣傳、無意義口頭語與常見雜訊。

### GUI

- PySide6 Windows 桌面介面。
- 支援 FHD、QHD、4K 等比例縮放。
- 支援：
  - Start
  - Pause
  - Resume
  - Stop
  - Copy
  - Save As
  - Open Output Folder
- 顯示目前階段、進度、經過時間與預估剩餘時間。
- 內建 Debug panel。
- 單支失敗不影響後續任務。

### 匯出

可輸出：

- `.txt`
- `.md`
- `.json`
- `.docx`

主要檔案預設存到：

```text
knowledge/
```

Metadata sidecar 預設存到：

```text
knowledge/_meta/
```

---

## 適合使用情境

### 學習筆記

把教學影片、課程、演講轉成逐字稿與摘要，保存到個人知識庫。

### 投資研究

整理：

- 台股解盤
- 阪田戰法
- 技術分析
- 財經訪談
- 法人籌碼
- 房貸與理財內容

### 工作會議

將會議錄音或影片轉成文字，再整理出：

- 重點
- 決策
- 風險
- 待辦事項

### 內容研究

批次處理大量影片，快速建立可搜尋的純文字資料。

### 心理與自我成長內容

保留理論骨架、論點、案例、建議與可能誇飾之處，而不是只產生簡短雞湯式摘要。

---

## 系統需求

### 建議環境

- Windows 10 / Windows 11 64-bit
- Python 3.11 或 3.12
- 16 GB RAM 以上
- 20 GB 以上可用磁碟空間
- NVIDIA GPU 建議 8 GB VRAM 以上
- RTX 3060 或更高階 GPU 可使用 CUDA 加速

### 必要元件

- Python
- Node.js
- FFmpeg
- Ollama
- faster-whisper 本機模型

### Python 版本

建議：

```text
Python 3.11.x
Python 3.12.x
```

避免使用來源不明或過度修改的 Python 發行版。

---

## 安裝方式

### 1. 下載專案

```powershell
git clone <YOUR_REPOSITORY_URL>
```

進入專案：

```powershell
cd C:\Users\Rossi\Documents\Claude\Media2Txt-Pro
```

### 2. 安裝 Python 依賴

家用電腦使用系統 Python：

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

公司電腦使用 `.venv`：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`run.bat` 會優先使用：

```text
.venv\Scripts\python.exe
```

若不存在，才使用系統 Python。

### 3. 安裝 Node.js

Node.js 供 `yt-dlp` 處理 YouTube 部分 JavaScript 驗證。

安裝後檢查：

```powershell
node -v
```

### 4. 準備 FFmpeg

程式會依序偵測：

1. 系統 `PATH`
2. 專案內 `tools\ffmpeg\x64`
3. 專案內 `tools\ffmpeg\bin`
4. 上層共用 `tools\ffmpeg`
5. JDownloader 2 的 FFmpeg：

```text
%LOCALAPPDATA%\JDownloader 2.0\tools\Windows\ffmpeg\x64
```

手動測試：

```powershell
ffmpeg -version
```

或：

```powershell
& "C:\Users\Rossi\AppData\Local\JDownloader 2.0\tools\Windows\ffmpeg\x64\ffmpeg.exe" -version
```

---

## Whisper 模型設定

### 建議模型位置

專案同層共用模型：

```text
C:\Users\Rossi\Documents\Claude\models\faster-whisper-large-v3
```

或專案內：

```text
Media2Txt-Pro\models\faster-whisper-large-v3
```

模型目錄至少應包含：

```text
model.bin
config.json
tokenizer.json
vocabulary.json
preprocessor_config.json
```

### 手動指定模型

PowerShell：

```powershell
$env:WHISPER_MODEL_DIR="C:\Users\Rossi\Documents\Claude\models\faster-whisper-large-v3"
```

CMD / BAT：

```bat
set "WHISPER_MODEL_DIR=C:\Users\Rossi\Documents\Claude\models\faster-whisper-large-v3"
```

---

## Ollama 摘要模型設定

### 安裝 Ollama

安裝完成後檢查：

```powershell
ollama --version
```

### 下載模型

繁體中文摘要建議：

```powershell
ollama pull qwen2.5:14b
```

英文摘要可使用：

```powershell
ollama pull llama3.1
```

查看目前模型：

```powershell
ollama list
```

查看是否有模型常駐 GPU：

```powershell
ollama ps
```

停止模型：

```powershell
ollama stop qwen2.5:14b
```

### 模型環境變數

```bat
set "OLLAMA_MODEL_ZH=qwen2.5:14b"
set "OLLAMA_MODEL_EN=llama3.1"
```

若 GPU VRAM 不足，可改用較小模型。

---

## 啟動方式

在專案根目錄執行：

```powershell
.\run.bat
```

`run.bat` 會自動：

1. 偵測 `.venv` 或系統 Python。
2. 尋找 Whisper 模型。
3. 尋找 FFmpeg。
4. 加入 NVIDIA CUDA DLL 路徑。
5. 設定離線模式。
6. 設定 GPU / CPU 轉錄模式。
7. 啟動 PySide6 GUI。
8. 程式關閉後清理暫存資料夾。

---

## 完整使用流程

### YouTube 批次

1. 執行 `run.bat`。
2. 選擇啟動模式。
3. 在左上方 YouTube URL 區域，每行貼一個網址。

範例：

```text
https://www.youtube.com/watch?v=xxxxxxxxxxx
https://youtu.be/yyyyyyyyyyy
```

4. 選擇摘要語言。
5. 按下 `Start`。
6. 程式會依序：
   - 取得影片資訊
   - 嘗試下載字幕
   - 下載音訊
   - 轉錄
   - 清理逐字稿
   - 產生摘要
   - 保存輸出
7. 完成後按 `Open Output Folder` 開啟 `knowledge/`。

### 本機影音批次

1. 按 `Add Local Video / Audio`。
2. 可一次選取多個檔案。
3. 選擇摘要語言。
4. 按 `Start`。
5. 程式會逐一轉錄與摘要。

### 混合批次

可以同時：

- 貼入多個 YouTube URL
- 加入多個本機影音檔

程式會按照任務順序逐筆處理。

### Pause / Resume / Stop

- `Pause`：在安全檢查點暫停。
- `Resume`：繼續處理。
- `Stop`：要求停止目前批次。

Whisper 或 FFmpeg 正在執行 native 工作時，停止可能不會瞬間生效，會在下一個安全點中止。

---

## 執行模式說明

`run.bat` 提供四種模式。

### 1. Auto / GPU Auto

建議日常使用。

特性：

- 優先 GPU
- GPU compute type：`int8_float16`
- GPU 失敗後自動改用 CPU
- CPU compute type：`int8`
- 啟用原生崩潰隔離
- 啟用 Chunk Recovery

### 2. CPU Only

完全不使用 CUDA。

適合：

- 沒有 NVIDIA GPU
- CUDA 環境不穩
- 需要最高穩定性
- 公司電腦僅有 CPU

缺點是速度較慢。

### 3. Low Resource

降低 GPU / CPU 負載。

適合：

- RTX 3060 長影片
- 顯存不足
- 系統 RAM 不足
- 一般模式曾發生 native crash
- 同時有 Ollama 模型常駐

會使用更低的 beam、best-of 與上下文設定。

### 4. GPU Check Only

只檢查：

- NVIDIA DLL
- CUDA runtime
- cuBLAS
- cuDNN
- Whisper GPU 能否載入

不執行完整轉錄。

---

## 輸出內容與目錄

### 主輸出

```text
knowledge/
```

檔名格式通常為：

```text
影片標題_YYYYMMDD_HHMMSS.txt
```

### Metadata

```text
knowledge/_meta/
```

Metadata 內容可能包含：

- title
- video_id
- media_source
- media_ref
- transcript_source
- subtitle_source
- summary_language
- is_music_like
- generated_at
- saved_at
- main_file
- main_file_name
- main_file_ext

### 暫存資料

```text
data/tmp/
data/cache/
data/downloads/
data/temp/
```

程式正常結束後，`run.bat` 會清理暫存資料。

不會清理：

```text
knowledge/
knowledge/_meta/
logs/
models/
```

---

## 轉錄處理流程

```text
輸入 YouTube URL 或本機影音
        ↓
取得影片資訊
        ↓
YouTube 有可用字幕？
   ├─ 是 → 使用字幕
   └─ 否 → 下載音訊
                ↓
        faster-whisper 轉錄
                ↓
     逐字稿清理與繁體轉換
                ↓
          Ollama 摘要
                ↓
       儲存 knowledge/ 與 _meta/
```

### YouTube 字幕策略

順序通常為：

1. 手動字幕
2. 自動字幕
3. Whisper

若字幕出現：

- HTTP 429
- HTTP 403
- timeout
- 無法下載字幕

程式會改成 audio-only 下載，避免整支影片直接失敗。

---

## GPU 原生閃退保護

Windows 上的 CTranslate2 / CUDA 有時不會拋出一般 Python exception，而是直接終止程序。

常見代碼：

```text
0xC0000005  Access Violation
0xC0000409  Stack Buffer Overrun
```

### 原本風險

```text
CUDA native crash
→ Python 主程序死亡
→ Qt GUI 關閉
→ 整批任務消失
```

### 目前保護方式

```text
Qt 主程序
    ↓
啟動獨立轉錄子程序
    ↓
GPU 子程序成功 → 回傳逐字稿
GPU 子程序崩潰 → 主 GUI 保持執行
    ↓
自動建立 CPU 子程序重試
```

預設設定：

```bat
MEDIA2TXT_TRANSCRIBE_SUBPROCESS=1
MEDIA2TXT_GPU_COMPUTE_TYPE=int8_float16
MEDIA2TXT_CPU_COMPUTE_TYPE=int8
MEDIA2TXT_LONG_VIDEO_MINUTES=15
MEDIA2TXT_VERY_LONG_VIDEO_MINUTES=40
```

---

## Chunk Recovery 切段救援

若發生以下狀況：

```text
GPU 子程序崩潰
CPU 整檔重試也失敗
invalid unordered_map<K, T> key
```

程式會進入 Chunk Recovery。

處理步驟：

1. 使用 FFmpeg 將音訊正規化為：
   - PCM WAV
   - 16 kHz
   - mono
2. 將音訊切成多段。
3. 每段使用全新的 CPU 子程序轉錄。
4. 優先嘗試 CPU `float32`。
5. 失敗時再嘗試 CPU `int8`。
6. 合併所有成功段落。

預設切段大小：

```bat
MEDIA2TXT_CHUNK_SECONDS=300
```

即每段五分鐘。

Chunk Recovery 使用較安全參數：

```text
beam_size=1
best_of=1
temperature=0.0
condition_on_previous_text=False
vad_filter=False
word_timestamps=False
```

這能降低單一長音訊 decoder state 累積造成的錯誤。

---

## 摘要處理方式

### 短內容

短逐字稿會直接交給 Ollama 產生最終摘要。

### 長內容

長逐字稿會：

1. 分割成多個文字 chunk。
2. 對每一段產生局部摘要。
3. 合併所有局部摘要。
4. 再產生最終完整摘要。

### 股票／金融摘要

會特別保留：

- 極端數據
- 成交量
- 外資與法人
- K 線判讀
- 支撐與壓力
- 條件分支
- 關鍵價位
- 可做與避開
- 操作結論
- 風險條件

### 投資教育摘要

會區分：

- 主張
- 假設
- 計算邏輯
- 實作方式
- 限制
- 風險

### 心理／自我成長摘要

會保留：

- 論點樹
- 理論框架
- 專有名詞
- 案例與比喻
- 可執行建議
- 可能誇飾或延伸之處

---

## 支援格式

### 本機影片

```text
.mp4
.mkv
.mov
.avi
.webm
```

### 本機音訊

```text
.mp3
.wav
.m4a
.flac
.aac
.ogg
```

### 輸出格式

```text
.txt
.md
.json
.docx
```

---

## 環境變數

### Whisper

```bat
WHISPER_MODEL_DIR
WHISPER_MODEL_NAME
WHISPER_DEVICE
MEDIA2TXT_OFFLINE
MEDIA2TXT_LOW_RESOURCE
MEDIA2TXT_TRANSCRIBE_LANGUAGE
```

### 效能與穩定性

```bat
MEDIA2TXT_TRANSCRIBE_SUBPROCESS
MEDIA2TXT_GPU_COMPUTE_TYPE
MEDIA2TXT_CPU_COMPUTE_TYPE
MEDIA2TXT_LONG_VIDEO_MINUTES
MEDIA2TXT_VERY_LONG_VIDEO_MINUTES
MEDIA2TXT_CHUNK_FALLBACK
MEDIA2TXT_CHUNK_SECONDS
```

### Ollama

```bat
OLLAMA_URL
OLLAMA_MODEL_ZH
OLLAMA_MODEL_EN
```

### 匯出

```bat
MEDIA2TXT_EXPORT_FORMAT
```

可使用：

```text
txt
md
json
docx
```

---

## 常見問題

### 1. 一支影片需要很久

先查看 Debug panel：

```text
device=cpu
compute_type=int8
```

若顯示 CPU，代表沒有使用 GPU。

可執行：

```powershell
.\run.bat
```

選擇：

```text
4. GPU Check Only
```

確認 CUDA 是否正常。

### 2. GPU 轉錄閃退

若看到：

```text
0xC0000005
0xC0000409
```

程式會由子程序隔離並改用 CPU。

建議：

1. 使用 `Low Resource`。
2. 執行前檢查 `ollama ps`。
3. 停止不需要的 Ollama 模型。
4. 關閉其他 GPU 應用程式。
5. 確保 NVIDIA driver 正常。

### 3. `invalid unordered_map<K, T> key`

這通常是 faster-whisper / CTranslate2 在特定音訊後段出現的內部錯誤。

新版會：

1. GPU 整檔嘗試
2. CPU 整檔嘗試
3. 音訊正規化
4. Chunk Recovery

### 4. 找不到 FFmpeg

確認：

```powershell
ffmpeg -version
```

若使用 JDownloader：

```text
C:\Users\<USERNAME>\AppData\Local\JDownloader 2.0\tools\Windows\ffmpeg\x64
```

確認裡面存在：

```text
ffmpeg.exe
ffprobe.exe
```

### 5. 找不到 Whisper 模型

確認：

```text
WHISPER_MODEL_DIR
```

並確認模型目錄包含必要檔案。

### 6. YouTube 下載失敗

更新 yt-dlp：

```powershell
python -m pip install --upgrade yt-dlp
```

若遇到登入或年齡限制，可在專案根目錄放置：

```text
cookies.txt
```

請勿把 `cookies.txt` commit 到 Git。

### 7. Ollama 摘要失敗

檢查：

```powershell
ollama list
ollama ps
```

確認 API：

```text
http://127.0.0.1:11434
```

確認模型名稱與環境變數一致。

### 8. 批次有一支失敗

程式會顯示：

```text
TASK FAILED
```

但仍繼續下一筆。

最後會顯示：

```text
Batch Summary
Total
Success
Failed
```

### 9. Git 顯示 LF / CRLF 警告

Windows 上常見：

```text
LF will be replaced by CRLF
```

通常不是程式錯誤。

但：

```text
trailing whitespace
```

會讓 `git diff --check` 失敗，需移除行尾空白。

---

## 專案結構

```text
Media2Txt-Pro/
├─ main.py
├─ run.bat
├─ requirements.txt
├─ README.md
├─ Install.txt
├─ How to use.txt
│
├─ ui/
│  └─ main_window.py
│
├─ pipeline/
│  ├─ cleaner.py
│  ├─ downloader.py
│  ├─ exporter.py
│  ├─ ffmpeg_utils.py
│  ├─ knowledge.py
│  ├─ summarizer.py
│  ├─ task.py
│  ├─ transcriber.py
│  ├─ transcribe_runner.py
│  ├─ updater.py
│  └─ worker.py
│
├─ knowledge/
│  └─ _meta/
│
├─ data/
│  ├─ tmp/
│  ├─ cache/
│  ├─ downloads/
│  └─ temp/
│
├─ logs/
└─ models/
```

### 主要模組

#### `main.py`

程式啟動入口與目前 GUI 工作流程。

#### `ui/main_window.py`

PySide6 主視窗與 FHD／4K 響應式 UI。

#### `pipeline/downloader.py`

負責：

- YouTube metadata
- 字幕
- 音訊下載
- 字幕失敗 fallback
- 本機檔案輸入

#### `pipeline/transcriber.py`

負責：

- faster-whisper
- CUDA / CPU
- 長影片策略
- 子程序隔離
- CPU fallback
- Chunk Recovery

#### `pipeline/transcribe_runner.py`

獨立轉錄子程序入口。

#### `pipeline/summarizer.py`

負責：

- Ollama API
- 領域判斷
- 分段摘要
- 最終合併
- 摘要品質控制

#### `pipeline/cleaner.py`

負責：

- 繁體中文轉換
- ASR 錯字修正
- 重複內容清理
- 宣傳與片尾雜訊清理

#### `pipeline/knowledge.py`

負責：

- 儲存主要輸出
- 檔名清理
- Metadata sidecar

#### `pipeline/exporter.py`

負責：

- TXT
- Markdown
- JSON
- DOCX

---

語法檢查：

```powershell
python -m py_compile main.py
python -m py_compile ui\main_window.py
python -m py_compile pipeline\transcriber.py
python -m py_compile pipeline\transcribe_runner.py
```

---

## 安全與使用限制

1. 僅處理你有權下載、轉錄或保存的內容。
2. YouTube、影音平台及原作者可能有各自的服務條款與著作權要求。
3. `cookies.txt` 可能包含帳號登入資訊，不得公開或提交到 Git。
4. Whisper 轉錄可能因口音、背景音、音樂或錄音品質產生錯字。
5. AI 摘要可能遺漏細節，重要內容仍需比對原始逐字稿。
6. 投資、醫療、法律摘要僅供內容整理，不應取代專業判斷。
7. Chunk Recovery 可能降低上下文連續性，但能提高特殊音訊的成功率。

---

## English summary

Media2Txt Pro Community is a Windows desktop application that converts YouTube videos and local media files into transcripts, AI-generated summaries, and reusable knowledge files.

Main capabilities:

- YouTube and local media batch processing
- Subtitle-first workflow
- faster-whisper GPU / CPU transcription
- Traditional Chinese and English summaries
- Local Ollama integration
- Native CUDA crash isolation
- Automatic CPU fallback
- FFmpeg audio normalization
- Chunk-based recovery for problematic media
- TXT, Markdown, JSON, and DOCX export
- Responsive FHD / 4K PySide6 GUI
- Per-task error isolation so one failure does not stop the batch

Start the application with:

```powershell
.\run.bat
```

Outputs are stored under:

```text
knowledge/
knowledge/_meta/
```
