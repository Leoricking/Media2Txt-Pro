import subprocess
import sys

def update_ytdlp():
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            check=True
        )
        print("yt-dlp 更新完成")
    except Exception as e:
        print(f"更新失敗: {e}")