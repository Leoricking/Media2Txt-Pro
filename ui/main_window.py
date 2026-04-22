import os
import locale

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, QTimer
from PySide6.QtGui import QTextCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QProgressBar,
    QLabel,
    QFrame,
    QFileDialog,
    QMessageBox,
    QApplication,
    QComboBox,
)

from pipeline.cleaner import clean_summary, clean_transcript, looks_too_short, to_traditional_chinese
from pipeline.ffmpeg_utils import get_ffmpeg_info


def detect_system_language() -> str:
    try:
        lang = locale.getlocale()[0]
    except Exception:
        lang = None

    if not lang:
        lang = os.environ.get("LANG", "")

    lang = (lang or "").lower()

    if "zh" in lang:
        return "zh"
    return "en"


class UIStrings:
    def __init__(self):
        self.lang = detect_system_language()

        if self.lang == "zh":
            self.window_title = "Media2Txt Pro"
            self.env_title = "環境狀態"
            self.input_title = "YouTube 連結（每行一個）"
            self.local_files_title = "本機影片 / 音訊檔（可批次上傳）"
            self.progress_title = "進度"
            self.result_title = "結果"
            self.summary_lang_title = "Summary 語言"

            self.start = "開始"
            self.stop = "停止"
            self.add_files = "加入本機影片 / 音訊"
            self.clear_files = "清空本機清單"
            self.save = "另存新檔"
            self.copy = "一鍵複製"
            self.open_folder = "開啟輸出資料夾"

            self.placeholder = "https://youtube.com/...\nhttps://youtube.com/...\n..."
            self.idle = "待命"
            self.preparing = "準備中..."
            self.please_input = "請先輸入 YouTube 連結，或加入本機影片 / 音訊檔"
            self.stopping = "停止中..."
            self.stopped = "已停止"
            self.done = "全部完成"

            self.downloading = "下載中"
            self.transcribing = "轉錄中"
            self.summarizing = "摘要中"

            self.transcript = "原文 transcript"
            self.summary = "摘要 summary"
            self.saved_to = "已儲存到"
            self.video_title = "影片標題"
            self.video_url = "影片連結"
            self.transcript_source = "Transcript 來源"
            self.media_source = "媒體來源"

            self.no_result = "目前沒有可儲存的結果"
            self.saved_ok = "已另存新檔"
            self.copy_ok = "結果已複製到剪貼簿"
            self.open_folder_fail = "無法開啟輸出資料夾"
            self.save_dialog_title = "另存結果"
            self.save_filter = "Text Files (*.txt);;All Files (*.*)"
            self.error = "錯誤"

            self.ffmpeg_found = "已偵測到 ffmpeg"
            self.ffmpeg_missing = "未安裝 ffmpeg，音訊時間戳修正與部份轉檔最佳化將不可用"
            self.ffmpeg_path = "ffmpeg 路徑"

            self.ready_for_new_input = "可貼上新的 YouTube 連結"

            self.source_manual_sub = "YouTube 手動字幕"
            self.source_auto_sub = "YouTube 自動字幕"
            self.source_whisper = "Whisper 語音辨識"
            self.source_whisper_music = "Whisper 語音辨識（音樂模式）"

            self.source_youtube = "YouTube URL"
            self.source_local = "本機檔案"

            self.low_confidence_note = "注意：此影片未取得字幕，且屬音樂/歌詞類內容，Whisper 文字稿可能不完整。"

            self.local_file_count = "已加入本機檔案數"
            self.file_dialog_title = "選擇影片 / 音訊檔"
            self.file_dialog_filter = (
                "Media Files (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.m4a *.flac *.aac *.ogg);;"
                "Video Files (*.mp4 *.mkv *.mov *.avi *.webm);;"
                "Audio Files (*.mp3 *.wav *.m4a *.flac *.aac *.ogg);;"
                "All Files (*.*)"
            )

            self.summary_lang_zh = "中文（繁體）"
            self.summary_lang_en = "英文"
        else:
            self.window_title = "Media2Txt Pro"
            self.env_title = "Environment"
            self.input_title = "YouTube URLs (one per line)"
            self.local_files_title = "Local Video / Audio Files (batch supported)"
            self.progress_title = "Progress"
            self.result_title = "Results"
            self.summary_lang_title = "Summary Language"

            self.start = "Start"
            self.stop = "Stop"
            self.add_files = "Add Local Video / Audio"
            self.clear_files = "Clear Local List"
            self.save = "Save As"
            self.copy = "Copy"
            self.open_folder = "Open Output Folder"

            self.placeholder = "https://youtube.com/...\nhttps://youtube.com/...\n..."
            self.idle = "Idle"
            self.preparing = "Preparing..."
            self.please_input = "Please enter at least one YouTube URL or add local media files"
            self.stopping = "Stopping..."
            self.stopped = "Stopped"
            self.done = "All completed"

            self.downloading = "Downloading"
            self.transcribing = "Transcribing"
            self.summarizing = "Summarizing"

            self.transcript = "Transcript"
            self.summary = "Summary"
            self.saved_to = "Saved to"
            self.video_title = "Video Title"
            self.video_url = "Video URL"
            self.transcript_source = "Transcript Source"
            self.media_source = "Media Source"

            self.no_result = "There is no result to save"
            self.saved_ok = "File saved"
            self.copy_ok = "Copied to clipboard"
            self.open_folder_fail = "Cannot open output folder"
            self.save_dialog_title = "Save Result"
            self.save_filter = "Text Files (*.txt);;All Files (*.*)"
            self.error = "Error"

            self.ffmpeg_found = "ffmpeg detected"
            self.ffmpeg_missing = "ffmpeg is not installed. Timestamp fixing and some conversion optimizations will be unavailable"
            self.ffmpeg_path = "ffmpeg path"

            self.ready_for_new_input = "Ready for new YouTube URLs"

            self.source_manual_sub = "YouTube manual subtitles"
            self.source_auto_sub = "YouTube auto subtitles"
            self.source_whisper = "Whisper speech recognition"
            self.source_whisper_music = "Whisper speech recognition (music mode)"

            self.source_youtube = "YouTube URL"
            self.source_local = "Local file"

            self.low_confidence_note = "Note: No subtitles were found for this music/lyric video, so the Whisper transcript may be incomplete."

            self.local_file_count = "Local files added"
            self.file_dialog_title = "Select video / audio files"
            self.file_dialog_filter = (
                "Media Files (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.m4a *.flac *.aac *.ogg);;"
                "Video Files (*.mp4 *.mkv *.mov *.avi *.webm);;"
                "Audio Files (*.mp3 *.wav *.m4a *.flac *.aac *.ogg);;"
                "All Files (*.*)"
            )

            self.summary_lang_zh = "Chinese (Traditional)"
            self.summary_lang_en = "English"


class WorkerSignals(QObject):
    progress = Signal(int)
    status = Signal(str)
    result = Signal(str)
    finished = Signal()
    failed = Signal(str)


class Worker(QRunnable):
    def __init__(self, tasks, stop_flag, ui_strings: UIStrings, summary_language: str):
        super().__init__()
        self.tasks = tasks
        self.stop_flag = stop_flag
        self.s = ui_strings
        self.summary_language = summary_language
        self.signals = WorkerSignals()

    def run(self):
        try:
            from pipeline.downloader import download_audio, process_local_media
            from pipeline.transcriber import transcribe
            from pipeline.summarizer import summarize
            from pipeline.knowledge import save_note

            total = len(self.tasks)

            for i, task in enumerate(self.tasks):
                if self.stop_flag.get("stop"):
                    self.signals.status.emit(f"🛑 {self.s.stopped}")
                    self.signals.finished.emit()
                    return

                task_type = task["type"]

                if task_type == "youtube":
                    url = task["value"]

                    self.signals.progress.emit(0)
                    self.signals.status.emit(f"[{i+1}/{total}] {self.s.downloading}")
                    media_info = download_audio(url, self.signals.progress.emit, self.stop_flag)

                    media_source = self.s.source_youtube
                    media_ref = url

                elif task_type == "local":
                    local_path = task["value"]
                    media_info = process_local_media(local_path)

                    media_source = self.s.source_local
                    media_ref = local_path

                else:
                    raise Exception(f"Unknown task type: {task_type}")

                audio_path = media_info["audio_path"]
                video_title = to_traditional_chinese(media_info["title"])
                video_id = media_info["video_id"]
                subtitle_text = media_info.get("subtitle_text", "") or ""
                subtitle_source = media_info.get("subtitle_source", "") or ""
                is_music_like = media_info.get("is_music_like", False)

                if self.stop_flag.get("stop"):
                    self.signals.status.emit(f"🛑 {self.s.stopped}")
                    self.signals.finished.emit()
                    return

                transcript = ""
                transcript_source = ""

                if subtitle_text.strip():
                    transcript = clean_transcript(subtitle_text)
                    if subtitle_source == "manual":
                        transcript_source = self.s.source_manual_sub
                    else:
                        transcript_source = self.s.source_auto_sub
                else:
                    self.signals.progress.emit(0)
                    self.signals.status.emit(f"[{i+1}/{total}] {self.s.transcribing}")
                    transcript = transcribe(
                        audio_path,
                        self.signals.progress.emit,
                        self.stop_flag,
                        is_music_like=is_music_like,
                    )
                    transcript = clean_transcript(transcript)
                    transcript_source = self.s.source_whisper_music if is_music_like else self.s.source_whisper

                low_confidence_warning = ""
                if is_music_like and not subtitle_text.strip() and looks_too_short(transcript):
                    low_confidence_warning = self.s.low_confidence_note

                if self.stop_flag.get("stop"):
                    self.signals.status.emit(f"🛑 {self.s.stopped}")
                    self.signals.finished.emit()
                    return

                self.signals.progress.emit(0)
                self.signals.status.emit(f"[{i+1}/{total}] {self.s.summarizing}")

                summary_input = transcript
                if low_confidence_warning:
                    summary_input = f"{low_confidence_warning}\n\n{transcript}"

                summary = summarize(
                    title=video_title,
                    transcript=summary_input,
                    transcript_source=transcript_source,
                    media_source=media_source,
                    summary_language=self.summary_language,
                    stop_flag=self.stop_flag,
                )

                if self.summary_language == "zh":
                    summary = clean_summary(summary)
                else:
                    summary = summary.strip()

                final_text = (
                    f"=== {video_title} ===\n\n"
                    f"[{self.s.media_source}] {media_source}\n"
                    f"[{self.s.video_url}] {media_ref}\n"
                    f"[{self.s.transcript_source}] {transcript_source}\n"
                )

                if low_confidence_warning:
                    final_text += f"[Warning] {to_traditional_chinese(low_confidence_warning)}\n"

                final_text += (
                    f"\n[{self.s.transcript}]\n"
                    f"{transcript}\n\n"
                    f"[{self.s.summary}]\n"
                    f"{summary}\n"
                )

                saved_path = save_note(video_title, final_text, video_id=video_id)
                final_text += f"\n[{self.s.saved_to}] {saved_path}\n"

                self.signals.result.emit(final_text)

            self.signals.progress.emit(100)
            self.signals.status.emit(f"✅ {self.s.done}")
            self.signals.finished.emit()

        except Exception as e:
            msg = str(e)
            self.signals.status.emit(f"❌ {msg}")
            self.signals.failed.emit(msg)
            self.signals.finished.emit()


class SectionCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("sectionCard")

        self.layout_main = QVBoxLayout()
        self.layout_main.setContentsMargins(14, 12, 14, 14)
        self.layout_main.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionTitle")

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        self.layout_main.addWidget(self.title_label)
        self.layout_main.addLayout(self.content_layout)
        self.setLayout(self.layout_main)

    def addWidget(self, widget):
        self.content_layout.addWidget(widget)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.ui = UIStrings()
        self.last_result_text = ""
        self.current_worker = None
        self.is_running = False
        self.local_files = []

        self.resize(860, 800)
        self.setMinimumSize(640, 600)

        self.pool = QThreadPool()
        self.stop_flag = {"stop": False}

        self._build_ui()
        self._bind_shortcuts()
        QTimer.singleShot(0, self._after_ui_ready)

    def _build_ui(self):
        self.setWindowTitle(self.ui.window_title)

        root = QVBoxLayout()
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.env_card = SectionCard(self.ui.env_title)
        self.ffmpeg_label = QLabel("")
        self.ffmpeg_label.setWordWrap(True)
        self.ffmpeg_label.setObjectName("envLabel")
        self.env_card.addWidget(self.ffmpeg_label)

        self.input_card = SectionCard(self.ui.input_title)
        self.input = QTextEdit()
        self.input.setPlaceholderText(self.ui.placeholder)
        self.input.setMinimumHeight(100)
        self.input.setMaximumHeight(140)
        self.input.setAcceptRichText(False)
        self.input_card.addWidget(self.input)

        self.local_card = SectionCard(self.ui.local_files_title)

        local_tools = QHBoxLayout()
        self.add_files_btn = QPushButton(self.ui.add_files)
        self.clear_files_btn = QPushButton(self.ui.clear_files)
        self.add_files_btn.setMinimumHeight(38)
        self.clear_files_btn.setMinimumHeight(38)

        local_tools.addWidget(self.add_files_btn)
        local_tools.addWidget(self.clear_files_btn)

        self.local_files_info = QLabel(f"{self.ui.local_file_count}: 0")
        self.local_files_info.setObjectName("envLabel")

        self.local_files_box = QTextEdit()
        self.local_files_box.setReadOnly(True)
        self.local_files_box.setMinimumHeight(90)
        self.local_files_box.setMaximumHeight(120)

        self.local_card.addLayout(local_tools)
        self.local_card.addWidget(self.local_files_info)
        self.local_card.addWidget(self.local_files_box)

        self.summary_lang_card = SectionCard(self.ui.summary_lang_title)
        summary_lang_layout = QHBoxLayout()

        self.summary_lang_combo = QComboBox()
        self.summary_lang_combo.addItem(self.ui.summary_lang_zh, "zh")
        self.summary_lang_combo.addItem(self.ui.summary_lang_en, "en")
        self.summary_lang_combo.setMinimumHeight(36)

        summary_lang_layout.addWidget(self.summary_lang_combo)
        self.summary_lang_card.addLayout(summary_lang_layout)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.start_btn = QPushButton(f"🚀 {self.ui.start}")
        self.stop_btn = QPushButton(f"🛑 {self.ui.stop}")
        self.start_btn.setMinimumHeight(42)
        self.stop_btn.setMinimumHeight(42)

        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)

        self.progress_card = SectionCard(self.ui.progress_title)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)

        self.status = QLabel(self.ui.idle)
        self.status.setObjectName("statusLabel")

        self.progress_card.addWidget(self.progress)
        self.progress_card.addWidget(self.status)

        result_tools = QHBoxLayout()
        result_tools.setSpacing(10)

        self.save_btn = QPushButton(self.ui.save)
        self.copy_btn = QPushButton(self.ui.copy)
        self.open_folder_btn = QPushButton(self.ui.open_folder)

        self.save_btn.setMinimumHeight(36)
        self.copy_btn.setMinimumHeight(36)
        self.open_folder_btn.setMinimumHeight(36)

        result_tools.addWidget(self.save_btn)
        result_tools.addWidget(self.copy_btn)
        result_tools.addWidget(self.open_folder_btn)

        self.result_card = SectionCard(self.ui.result_title)
        self.result_card.addLayout(result_tools)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(260)

        self.result_card.addWidget(self.output)

        root.addWidget(self.env_card)
        root.addWidget(self.input_card)
        root.addWidget(self.local_card)
        root.addWidget(self.summary_lang_card)
        root.addLayout(action_layout)
        root.addWidget(self.progress_card)
        root.addWidget(self.result_card)

        self.setLayout(root)

        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.save_btn.clicked.connect(self.save_result_as)
        self.copy_btn.clicked.connect(self.copy_result)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.add_files_btn.clicked.connect(self.add_local_files)
        self.clear_files_btn.clicked.connect(self.clear_local_files)

        self.setStyleSheet("""
            QWidget {
                font-size: 13px;
                background-color: #f4f6f8;
            }

            QFrame#sectionCard {
                background-color: #ffffff;
                border: 1px solid #d8dee4;
                border-radius: 10px;
            }

            QLabel#sectionTitle {
                font-size: 14px;
                font-weight: 700;
                color: #20262e;
                background: transparent;
            }

            QLabel#statusLabel {
                color: #4b5563;
                background: transparent;
            }

            QLabel#envLabel {
                color: #374151;
                background: transparent;
            }

            QTextEdit, QComboBox {
                background-color: #ffffff;
                border: 1px solid #cfd6dd;
                border-radius: 8px;
                padding: 8px;
            }

            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #45a049;
            }

            QPushButton:pressed {
                background-color: #3e9142;
            }

            QPushButton:disabled {
                background-color: #a5d6a7;
                color: #eef7ee;
            }

            QProgressBar {
                border: 1px solid #cfd6dd;
                border-radius: 8px;
                text-align: center;
                background-color: #ffffff;
                min-height: 28px;
            }

            QProgressBar::chunk {
                background-color: #08b625;
                border-radius: 7px;
            }
        """)

    def _bind_shortcuts(self):
        self.paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        self.paste_shortcut.activated.connect(self.focus_input_for_paste)

    def _after_ui_ready(self):
        self.status.setText(self.ui.idle)
        self.refresh_environment_status()
        self._set_running_state(False)
        self.refresh_local_files_display()

    def refresh_environment_status(self):
        ffmpeg_info = get_ffmpeg_info()
        if ffmpeg_info["installed"]:
            text = (
                f"✅ {self.ui.ffmpeg_found}\n"
                f"{self.ui.ffmpeg_path}: {ffmpeg_info['ffmpeg_path']}"
            )
        else:
            text = f"⚠️ {self.ui.ffmpeg_missing}"
        self.ffmpeg_label.setText(text)

    def refresh_local_files_display(self):
        self.local_files_info.setText(f"{self.ui.local_file_count}: {len(self.local_files)}")
        self.local_files_box.setPlainText("\n".join(self.local_files))

    def _set_running_state(self, running: bool):
        self.is_running = running

        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.add_files_btn.setEnabled(not running)
        self.clear_files_btn.setEnabled(not running)
        self.summary_lang_combo.setEnabled(not running)

        self.input.setReadOnly(running)
        self.input.setEnabled(True)

        if not running:
            self.input.setFocus()
            self.input.activateWindow()

    def focus_input_for_paste(self):
        if not self.is_running:
            self.input.setFocus()
            self.input.paste()

    def add_local_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.ui.file_dialog_title,
            "",
            self.ui.file_dialog_filter,
        )

        if not files:
            return

        existing = set(self.local_files)
        for f in files:
            if f not in existing:
                self.local_files.append(f)
                existing.add(f)

        self.refresh_local_files_display()

    def clear_local_files(self):
        self.local_files = []
        self.refresh_local_files_display()

    def build_tasks(self):
        tasks = []

        raw = self.input.toPlainText().strip()
        urls = [u.strip() for u in raw.splitlines() if u.strip()]
        for url in urls:
            tasks.append({"type": "youtube", "value": url})

        for file_path in self.local_files:
            tasks.append({"type": "local", "value": file_path})

        return tasks

    def start(self):
        tasks = self.build_tasks()
        if not tasks:
            self.status.setText(f"❌ {self.ui.please_input}")
            return

        self.output.clear()
        self.last_result_text = ""
        self.progress.setValue(0)
        self.stop_flag["stop"] = False
        self.status.setText(self.ui.preparing)

        summary_language = self.summary_lang_combo.currentData()

        worker = Worker(tasks, self.stop_flag, self.ui, summary_language)
        self.current_worker = worker

        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.status.connect(self.status.setText)
        worker.signals.result.connect(self.append_result)
        worker.signals.finished.connect(self.on_worker_finished)

        self._set_running_state(True)
        self.pool.start(worker)

    def stop(self):
        self.stop_flag["stop"] = True
        self.status.setText(f"🛑 {self.ui.stopping}")

    def on_worker_finished(self):
        self.current_worker = None
        self._set_running_state(False)

        if self.stop_flag["stop"]:
            self.status.setText(f"🛑 {self.ui.stopped}")
        else:
            self.status.setText(f"✅ {self.ui.done} · {self.ui.ready_for_new_input}")

    def append_result(self, text: str):
        if self.last_result_text:
            self.last_result_text += "\n" + text
        else:
            self.last_result_text = text

        self.output.append(text)
        self.output.moveCursor(QTextCursor.End)

    def save_result_as(self):
        if not self.last_result_text.strip():
            QMessageBox.information(self, self.ui.window_title, self.ui.no_result)
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.ui.save_dialog_title,
            "result.txt",
            self.ui.save_filter,
        )

        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.last_result_text)

        QMessageBox.information(self, self.ui.window_title, f"{self.ui.saved_ok}\n{file_path}")

    def copy_result(self):
        if not self.last_result_text.strip():
            QMessageBox.information(self, self.ui.window_title, self.ui.no_result)
            return

        QApplication.clipboard().setText(self.last_result_text)
        self.status.setText(f"✅ {self.ui.copy_ok}")

    def open_output_folder(self):
        from pipeline.knowledge import get_output_dir

        output_dir = get_output_dir()

        try:
            os.startfile(output_dir)
        except Exception as e:
            QMessageBox.warning(self, self.ui.error, f"{self.ui.open_folder_fail}\n{e}")