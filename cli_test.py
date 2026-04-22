import os
from pipeline.downloader import download_audio
from pipeline.transcriber import transcribe
from pipeline.summarizer import summarize
from pipeline.knowledge import save_note

# ===== 測試用網址 =====
URL = "https://www.youtube.com/watch?v=2heEKxMj1fk"

def log(msg):
    print(f"[LOG] {msg}")

def progress(stage, p):
    print(f"[{stage}] {p}%")

def main():
    print("=== START TEST ===")

    # ===== 1. 下載 =====
    log("下載中...")
    audio = download_audio(URL, lambda p: progress("下載", p))

    if not os.path.exists(audio):
        print("❌ 下載失敗")
        return

    log(f"下載完成: {audio}")

    # ===== 2. 轉錄 =====
    log("轉錄中...")
    text = transcribe(audio, lambda p: progress("轉錄", p))

    if not text.strip():
        print("❌ 轉錄失敗")
        return

    log(f"轉錄完成（長度 {len(text)}）")

    # ===== 3. 摘要 =====
    log("摘要中...")
    summary = summarize(text)

    log("摘要完成")

    # ===== 4. 儲存 =====
    full = f"\n=== 原文 ===\n{text}\n\n=== 摘要 ===\n{summary}\n"
    save_note(URL, full)

    print("\n=== RESULT ===")
    print(summary[:500])

    print("\n✅ 完整流程成功")

if __name__ == "__main__":
    main()