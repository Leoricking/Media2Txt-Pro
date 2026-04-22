from PySide6.QtCore import QObject, Signal, QRunnable
from pipeline.downloader import download_audio
from pipeline.transcriber import transcribe
from pipeline.summarizer import summarize
from pipeline.knowledge import save_note

class Signals(QObject):
    progress = Signal(int)
    status = Signal(str)
    result = Signal(str)
    finished = Signal()

class Task(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = Signals()
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        try:
            if not self.running: return

            self.signals.status.emit("下載中")
            audio = download_audio(self.url, lambda p: self.signals.progress.emit(int(p*0.5)))

            if not self.running: return

            self.signals.status.emit("轉錄中")
            text = transcribe(audio, lambda p: self.signals.progress.emit(50 + int(p*0.3)))

            if not self.running: return

            self.signals.status.emit("AI 摘要")
            summary = summarize(text)

            full = f"\n=== 原文 ===\n{text}\n\n=== 摘要 ===\n{summary}\n"
            save_note(self.url, full)

            self.signals.result.emit(full)
            self.signals.progress.emit(100)
            self.signals.status.emit("完成")

        except Exception as e:
            self.signals.status.emit(f"錯誤: {e}")

        self.signals.finished.emit()