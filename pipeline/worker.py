from PySide6.QtCore import QThread, Signal
from pipeline.downloader import download_audio_with_progress
from pipeline.transcriber import transcribe_with_progress

class Worker(QThread):
    progress = Signal(int)
    log = Signal(str)
    status = Signal(str)
    finished = Signal()

    def __init__(self, urls):
        super().__init__()
        self.urls = urls

    def run(self):
        total = len(self.urls)

        for i, url in enumerate(self.urls):
            base_progress = int((i / total) * 100)

            try:
                self.status.emit(f"[{i+1}/{total}] 下載中")

                # ===== 下載（0~50%）=====
                def dl_progress(p):
                    self.progress.emit(base_progress + int(p * 0.5))

                audio = download_audio_with_progress(url, dl_progress)

                self.status.emit("轉文字中")

                # ===== 轉錄（50~100%）=====
                def tr_progress(p):
                    self.progress.emit(base_progress + 50 + int(p * 0.5))

                text = transcribe_with_progress(audio, tr_progress)

                self.log.emit(f"\n=== {url} ===\n{text[:200]}...\n")

            except Exception as e:
                self.log.emit(f"錯誤: {url} -> {e}")

        self.progress.emit(100)
        self.status.emit("完成")
        self.finished.emit()