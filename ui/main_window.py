import os
import locale
import time
import re
from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, QTimer, Qt
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
    QSizePolicy,
    QSplitter,
    QCheckBox,
)

from pipeline.cleaner import clean_summary, clean_transcript, looks_too_short, to_traditional_chinese
from pipeline.ffmpeg_utils import get_ffmpeg_info
from pipeline.exporter import build_export_payload, export_by_extension


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


def detect_whisper_environment():
    info = {
        "faster_whisper_installed": False,
        "ctranslate2_installed": False,
        "models_found": [],
        "preferred_model_dir": "",
        "offline_mode": os.environ.get("MEDIA2TXT_OFFLINE", "0") == "1",
        "error": "",
        "cuda_ready": False,
        "cuda_reason": "",
    }

    try:
        import faster_whisper  # noqa: F401
        info["faster_whisper_installed"] = True
    except Exception as e:
        info["error"] = str(e)

    try:
        import ctranslate2  # noqa: F401
        info["ctranslate2_installed"] = True
    except Exception:
        pass

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        os.environ.get("WHISPER_MODEL_DIR", "").strip(),
        os.path.join(base_dir, "models", "faster-whisper-large-v3"),
        os.path.join("models", "faster-whisper-large-v3"),
        os.path.join(base_dir, "models", "faster-whisper-medium"),
        os.path.join(base_dir, "models", "faster-whisper-small"),
    ]

    checked = []
    required_files = [
        "model.bin",
        "config.json",
        "preprocessor_config.json",
        "tokenizer.json",
        "vocabulary.json",
    ]

    for path in candidates:
        if not path:
            continue
        norm = os.path.abspath(path)
        if norm in checked:
            continue
        checked.append(norm)

        if os.path.isdir(norm):
            if all(os.path.exists(os.path.join(norm, name)) for name in required_files):
                info["models_found"].append(norm)

    if info["models_found"]:
        info["preferred_model_dir"] = info["models_found"][0]

    try:
        from pipeline.transcriber import can_use_cuda_for_transcribe
        ready, cuda_info = can_use_cuda_for_transcribe()
        info["cuda_ready"] = ready
        info["cuda_reason"] = cuda_info.get("reason", "")
    except Exception as e:
        info["cuda_ready"] = False
        info["cuda_reason"] = str(e)

    return info


class UIStrings:
    def __init__(self):
        self.lang = detect_system_language()

        self.window_title = "Media2Txt Pro Community"
        self.env_title = "Environment"
        self.input_title = "YouTube URLs (one per line)"
        self.local_files_title = "Local Video / Audio Files (batch supported)"
        self.progress_title = "Progress"
        self.result_title = "Results"
        self.summary_lang_title = "Summary Language"
        self.debug_title = "Debug Status"

        self.start = "Start"
        self.pause = "Pause"
        self.resume = "Resume"
        self.stop = "Stop"
        self.add_files = "Add Local Video / Audio"
        self.clear_files = "Clear Local List"
        self.save = "Save As"
        self.copy = "Copy"
        self.open_folder = "Open Output Folder"
        self.clear_debug = "Clear Debug Log"
        self.show_debug = "Show Debug Panel"

        self.placeholder = "https://youtube.com/...\nhttps://youtube.com/...\n..."
        self.idle = "Idle"
        self.preparing = "Preparing..."
        self.please_input = "Please enter at least one YouTube URL or add local media files"
        self.pausing = "Pausing..."
        self.paused = "Paused"
        self.resuming = "Resuming..."
        self.stopping = "Stopping..."
        self.stopped = "Stopped"
        self.done = "All completed"
        self.done_with_error = "Finished with error"

        self.downloading = "Downloading"
        self.transcribing = "Transcribing"
        self.summarizing = "Summarizing"

        self.transcript = "Transcript"
        self.summary = "Summary"
        self.saved_to = "Saved to"
        self.video_url = "Video URL"
        self.transcript_source = "Transcript Source"
        self.media_source = "Media Source"

        self.no_result = "There is no result to save"
        self.saved_ok = "File saved"
        self.copy_ok = "Copied to clipboard"
        self.open_folder_fail = "Cannot open output folder"
        self.save_dialog_title = "Save Result"
        self.save_filter = (
            "Text Files (*.txt);;"
            "Markdown Files (*.md);;"
            "JSON Files (*.json);;"
            "Word Documents (*.docx);;"
            "All Files (*.*)"
        )
        self.error = "Error"

        self.ffmpeg_found = "ffmpeg detected"
        self.ffmpeg_missing = "ffmpeg is not installed. Timestamp fixing and some conversion optimizations will be unavailable"
        self.ffmpeg_path = "ffmpeg path"

        self.env_checking = "Checking environment..."
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

    def build_transcribe_error_message(self, raw_message: str) -> str:
        msg = (raw_message or "").strip()
        lower = msg.lower()

        if "no module named 'faster_whisper'" in lower:
            return (
                "Missing faster-whisper package.\n\nPlease run:\npip install -r requirements.txt\n\n"
                f"Original error:\n{msg}"
            )

        if "certificate_verify_failed" in lower or "self-signed certificate" in lower:
            return (
                "Whisper model download failed due to SSL certificate verification issues.\n\n"
                "Recommended actions:\n1. Use a local model\n2. Set WHISPER_MODEL_DIR\n3. Enable offline mode with MEDIA2TXT_OFFLINE=1\n\n"
                f"Original error:\n{msg}"
            )

        return msg


class WorkerSignals(QObject):
    progress = Signal(int)
    status = Signal(str)
    result = Signal(str)
    finished = Signal(bool)
    failed = Signal(str)
    debug = Signal(str)


class EnvironmentCheckSignals(QObject):
    finished = Signal(dict)
    failed = Signal(str)


class EnvironmentCheckWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = EnvironmentCheckSignals()

    def run(self):
        try:
            ffmpeg_info = get_ffmpeg_info()
            whisper_info = detect_whisper_environment()
            self.signals.finished.emit({
                "ffmpeg_info": ffmpeg_info,
                "whisper_info": whisper_info,
            })
        except Exception as e:
            self.signals.failed.emit(str(e))


class Worker(QRunnable):
    def __init__(self, tasks, control_flag, ui_strings: UIStrings, summary_language: str):
        super().__init__()
        self.tasks = tasks
        self.control_flag = control_flag
        self.s = ui_strings
        self.summary_language = summary_language
        self.signals = WorkerSignals()
        self.had_error = False

    def dbg(self, text: str):
        print(text)
        self.signals.debug.emit(text)

    def is_stopped(self):
        return bool(self.control_flag.get("stop"))

    def wait_if_paused(self, status_text: str = ""):
        while self.control_flag.get("pause") and not self.is_stopped():
            if status_text:
                self.signals.status.emit(status_text)
            time.sleep(0.15)

    def _emit_task_failure(self, index: int, total: int, task_ref: str, error: Exception):
        self.had_error = True
        msg = str(error)
        self.dbg(f"TASK ERROR {index}/{total}: {task_ref} :: {msg}")
        block = (
            f"=== TASK FAILED [{index}/{total}] ===\n\n"
            f"[Task] {task_ref}\n"
            f"[Error] {msg}\n"
            f"[Action] This task was skipped. Batch continues with the next task.\n"
        )
        self.signals.result.emit(block)

    def _build_final_text(
        self,
        video_title: str,
        media_source: str,
        media_ref: str,
        transcript_source: str,
        transcript: str,
        summary: str,
        low_confidence_warning: str = "",
        summary_status: str = "ok",
        summary_error: str = "",
    ) -> str:
        final_text = (
            f"=== {video_title} ===\n\n"
            f"[{self.s.media_source}] {media_source}\n"
            f"[{self.s.video_url}] {media_ref}\n"
            f"[{self.s.transcript_source}] {transcript_source}\n"
        )

        if low_confidence_warning:
            final_text += f"[Warning] {to_traditional_chinese(low_confidence_warning)}\n"

        if summary_status != "ok":
            final_text += f"[Summary Status] {summary_status}\n"
            if summary_error:
                final_text += f"[Summary Error] {summary_error}\n"

        final_text += (
            f"\n[{self.s.transcript}]\n"
            f"{transcript}\n\n"
            f"[{self.s.summary}]\n"
            f"{summary}\n"
        )
        return final_text

    def run(self):
        try:
            self.dbg("START WORKER RUN")

            from pipeline.downloader import download_audio, process_local_media
            from pipeline.transcriber import transcribe, get_transcriber_runtime_info
            from pipeline.summarizer import summarize, build_fallback_summary
            from pipeline.knowledge import save_note

            runtime_info = get_transcriber_runtime_info()
            self.dbg(f"TRANSCRIBER RUNTIME: {runtime_info}")

            total = len(self.tasks)
            self.dbg(f"TASK TOTAL: {total}")

            success_count = 0
            failed_tasks = []
            fallback_tasks = []

            for i, task in enumerate(self.tasks):
                task_index = i + 1
                task_ref = task.get("value", "")

                if self.is_stopped():
                    self.signals.status.emit(self.s.stopped)
                    self.dbg("WORKER STOPPED BY USER")
                    self.signals.finished.emit(False)
                    return

                self.wait_if_paused(self.s.paused)

                try:
                    task_type = task["type"]
                    self.dbg(f"PROCESS TASK {task_index}/{total} TYPE={task_type}")

                    if task_type == "youtube":
                        url = task["value"]
                        task_ref = url
                        self.signals.progress.emit(0)
                        self.signals.status.emit(f"[{task_index}/{total}] {self.s.downloading}")
                        self.dbg(f"DOWNLOAD YOUTUBE: {url}")
                        media_info = download_audio(url, self.signals.progress.emit, self.control_flag)
                        media_source = self.s.source_youtube
                        media_ref = url

                    elif task_type == "local":
                        local_path = task["value"]
                        task_ref = local_path
                        self.signals.progress.emit(0)
                        self.signals.status.emit(f"[{task_index}/{total}] {self.s.transcribing}")
                        self.dbg(f"PROCESS LOCAL FILE: {local_path}")
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

                    self.dbg(f"TITLE: {video_title}")
                    self.dbg(f"AUDIO PATH: {audio_path}")
                    self.dbg(f"HAS SUBTITLE: {'YES' if subtitle_text.strip() else 'NO'}")
                    self.dbg(f"IS MUSIC LIKE: {is_music_like}")

                    if self.is_stopped():
                        self.signals.status.emit(self.s.stopped)
                        self.dbg("WORKER STOPPED BEFORE TRANSCRIBE")
                        self.signals.finished.emit(False)
                        return

                    self.wait_if_paused(self.s.paused)

                    transcript = ""
                    transcript_source = ""

                    if subtitle_text.strip():
                        transcript = clean_transcript(subtitle_text, force_traditional=(self.summary_language == "zh"))
                        transcript_source = self.s.source_manual_sub if subtitle_source == "manual" else self.s.source_auto_sub
                        self.dbg(f"USE SUBTITLE SOURCE: {transcript_source}")
                        self.signals.progress.emit(65)
                    else:
                        self.signals.progress.emit(0)
                        self.signals.status.emit(f"[{task_index}/{total}] {self.s.transcribing}")
                        self.dbg("CALL transcribe()")
                        transcript = transcribe(
                            audio_path=audio_path,
                            progress_callback=self.signals.progress.emit,
                            stop_flag=self.control_flag,
                            is_music_like=is_music_like,
                            debug_callback=self.dbg,
                        )
                        transcript = clean_transcript(transcript, force_traditional=(self.summary_language == "zh"))
                        transcript_source = self.s.source_whisper_music if is_music_like else self.s.source_whisper
                        self.dbg(f"TRANSCRIBE DONE, SOURCE: {transcript_source}")

                    low_confidence_warning = ""
                    if is_music_like and not subtitle_text.strip() and looks_too_short(transcript):
                        low_confidence_warning = self.s.low_confidence_note
                        self.dbg("LOW CONFIDENCE WARNING TRIGGERED")

                    if self.is_stopped():
                        self.signals.status.emit(self.s.stopped)
                        self.dbg("WORKER STOPPED BEFORE SUMMARY")
                        self.signals.finished.emit(False)
                        return

                    self.wait_if_paused(self.s.paused)

                    self.signals.progress.emit(85)
                    self.signals.status.emit(f"[{task_index}/{total}] {self.s.summarizing}")
                    self.dbg("CALL summarize()")

                    summary_input = transcript
                    if low_confidence_warning:
                        summary_input = f"{low_confidence_warning}\n\n{transcript}"

                    summary_status = "ok"
                    summary_error = ""

                    try:
                        summary = summarize(
                            title=video_title,
                            transcript=summary_input,
                            transcript_source=transcript_source,
                            media_source=media_source,
                            summary_language=self.summary_language,
                            stop_flag=self.control_flag,
                        )
                        summary = clean_summary(summary, summary_language=self.summary_language)
                        self.dbg("SUMMARY DONE")
                    except Exception as summary_exc:
                        if self.is_stopped():
                            raise
                        summary_error = str(summary_exc)
                        lower_error = summary_error.lower()
                        if "timed out" in lower_error or "read timeout" in lower_error or "timeout" in lower_error:
                            summary_status = "fallback_timeout"
                        else:
                            summary_status = "fallback_error"
                        self.had_error = True
                        fallback_tasks.append((task_index, task_ref, summary_status, summary_error))
                        self.dbg(f"SUMMARY FAILED, USE FALLBACK: {summary_status} :: {summary_error}")
                        summary = build_fallback_summary(
                            title=video_title,
                            transcript=transcript,
                            summary_error=summary_error,
                            summary_language=self.summary_language,
                            transcript_source=transcript_source,
                            media_source=media_source,
                        )
                        summary = clean_summary(summary, summary_language=self.summary_language)

                    metadata = {
                        "title": video_title,
                        "video_id": video_id,
                        "media_source": media_source,
                        "media_ref": media_ref,
                        "transcript_source": transcript_source,
                        "subtitle_source": subtitle_source,
                        "summary_language": self.summary_language,
                        "is_music_like": is_music_like,
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "transcript_status": "ok" if transcript.strip() else "empty",
                        "summary_status": summary_status,
                        "summary_error": summary_error,
                        "output_type": "full" if summary_status == "ok" else "fallback_summary",
                        "ollama_model_zh": os.environ.get("OLLAMA_MODEL_ZH", ""),
                        "ollama_model_en": os.environ.get("OLLAMA_MODEL_EN", ""),
                        "ollama_timeout_sec": os.environ.get("OLLAMA_TIMEOUT_SEC", "300"),
                    }

                    final_text = self._build_final_text(
                        video_title=video_title,
                        media_source=media_source,
                        media_ref=media_ref,
                        transcript_source=transcript_source,
                        transcript=transcript,
                        summary=summary,
                        low_confidence_warning=low_confidence_warning,
                        summary_status=summary_status,
                        summary_error=summary_error,
                    )

                    saved_path = save_note(
                        title=video_title,
                        content=final_text,
                        video_id=video_id,
                        metadata=metadata,
                        transcript=transcript,
                        summary=summary,
                    )
                    self.dbg(f"SAVED TO: {saved_path}")
                    final_text += f"\n[{self.s.saved_to}] {saved_path}\n"

                    self.signals.result.emit(final_text)
                    success_count += 1

                except Exception as task_exc:
                    if self.is_stopped():
                        self.signals.status.emit(self.s.stopped)
                        self.dbg("WORKER STOPPED DURING TASK")
                        self.signals.finished.emit(False)
                        return
                    failed_tasks.append((task_index, task_ref, str(task_exc)))
                    self._emit_task_failure(task_index, total, task_ref, task_exc)
                    continue

            summary_lines = [
                "=== Batch Summary ===",
                f"Total: {total}",
                f"Success: {success_count}",
                f"Failed: {len(failed_tasks)}",
                f"Fallback summaries: {len(fallback_tasks)}",
            ]

            if fallback_tasks:
                summary_lines.append("Fallback summary tasks:")
                for idx, ref, status, err in fallback_tasks:
                    summary_lines.append(f"- [{idx}/{total}] {ref}: {status} - {err}")

            if failed_tasks:
                summary_lines.append("Failed tasks:")
                for idx, ref, err in failed_tasks:
                    summary_lines.append(f"- [{idx}/{total}] {ref}: {err}")

            self.signals.result.emit("\n".join(summary_lines) + "\n")

            self.signals.progress.emit(100)
            if failed_tasks or fallback_tasks:
                self.signals.status.emit(self.s.done_with_error)
                self.dbg(f"WORKER FINISHED WITH TASK ERRORS success={success_count} failed={len(failed_tasks)} fallback={len(fallback_tasks)}")
                self.signals.finished.emit(False)
            else:
                self.signals.status.emit(self.s.done)
                self.dbg("WORKER FINISHED SUCCESS")
                self.signals.finished.emit(True)

        except Exception as e:
            self.had_error = True
            msg = str(e)
            self.dbg(f"WORKER ERROR: {msg}")
            self.signals.status.emit(f"❌ {msg}")
            self.signals.failed.emit(msg)
            self.signals.finished.emit(False)


class SectionCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("sectionCard")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionTitle")

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        outer.addWidget(self.title_label)
        outer.addLayout(self.content_layout)

    def addWidget(self, widget):
        self.content_layout.addWidget(widget)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)


class MainWindow(QWidget):
    TASK_PREFIX_RE = re.compile(r"^\[(\d+)/(\d+)\]\s*(.+?)\s*$")

    def __init__(self):
        super().__init__()

        self.ui = UIStrings()
        self.last_result_text = ""
        self.last_export_payload = None
        self.current_worker = None
        self.is_running = False
        self.local_files = []
        self.pool = QThreadPool()
        self.control_flag = {"stop": False, "pause": False}
        self.env_check_running = False

        self.task_start_ts = None
        self.last_progress_value = 0
        self.eta_timer = QTimer()
        self.eta_timer.timeout.connect(self.update_eta_display)
        self.last_run_had_error = False

        self.current_task_index = None
        self.current_task_total = None
        self.current_stage_name = ""
        self.current_status_text = self.ui.idle

        self.setMinimumSize(1100, 760)
        self.resize(1450, 900)

        self._build_ui()
        QTimer.singleShot(50, self._after_ui_ready)

    def _build_ui(self):
        self.setWindowTitle(self.ui.window_title)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.env_card = SectionCard(self.ui.env_title)
        self.ffmpeg_label = QLabel(self.ui.env_checking)
        self.ffmpeg_label.setWordWrap(True)
        self.ffmpeg_label.setObjectName("envLabel")
        self.env_card.addWidget(self.ffmpeg_label)
        root.addWidget(self.env_card)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.input_card = SectionCard(self.ui.input_title)
        self.input = QTextEdit()
        self.input.setPlaceholderText(self.ui.placeholder)
        self.input.setMinimumHeight(120)
        self.input.setAcceptRichText(False)
        self.input_card.addWidget(self.input)

        self.local_card = SectionCard(self.ui.local_files_title)
        local_tools = QHBoxLayout()

        self.add_files_btn = QPushButton(self.ui.add_files)
        self.clear_files_btn = QPushButton(self.ui.clear_files)
        self.add_files_btn.setMinimumHeight(40)
        self.clear_files_btn.setMinimumHeight(40)

        local_tools.addWidget(self.add_files_btn)
        local_tools.addWidget(self.clear_files_btn)

        self.local_files_info = QLabel(f"{self.ui.local_file_count}: 0")
        self.local_files_info.setObjectName("envLabel")

        self.local_files_box = QTextEdit()
        self.local_files_box.setReadOnly(True)
        self.local_files_box.setMinimumHeight(160)

        self.local_card.addLayout(local_tools)
        self.local_card.addWidget(self.local_files_info)
        self.local_card.addWidget(self.local_files_box)

        self.summary_lang_card = SectionCard(self.ui.summary_lang_title)
        summary_lang_layout = QHBoxLayout()
        self.summary_lang_combo = QComboBox()
        self.summary_lang_combo.addItem(self.ui.summary_lang_zh, "zh")
        self.summary_lang_combo.addItem(self.ui.summary_lang_en, "en")
        self.summary_lang_combo.setMinimumHeight(38)
        summary_lang_layout.addWidget(self.summary_lang_combo)
        self.summary_lang_card.addLayout(summary_lang_layout)

        action_card = SectionCard("")
        action_layout = QHBoxLayout()

        self.start_btn = QPushButton(self.ui.start)
        self.pause_btn = QPushButton(self.ui.pause)
        self.resume_btn = QPushButton(self.ui.resume)
        self.stop_btn = QPushButton(self.ui.stop)

        self.start_btn.setMinimumHeight(46)
        self.pause_btn.setMinimumHeight(46)
        self.resume_btn.setMinimumHeight(46)
        self.stop_btn.setMinimumHeight(46)

        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.pause_btn)
        action_layout.addWidget(self.resume_btn)
        action_layout.addWidget(self.stop_btn)
        action_card.addLayout(action_layout)

        debug_card = SectionCard(self.ui.debug_title)

        debug_toolbar = QHBoxLayout()
        self.show_debug_checkbox = QCheckBox(self.ui.show_debug)
        self.show_debug_checkbox.setChecked(True)
        self.clear_debug_btn = QPushButton(self.ui.clear_debug)
        self.clear_debug_btn.setMinimumHeight(34)

        debug_toolbar.addWidget(self.show_debug_checkbox)
        debug_toolbar.addStretch(1)
        debug_toolbar.addWidget(self.clear_debug_btn)

        self.debug_output = QTextEdit()
        self.debug_output.setReadOnly(True)
        self.debug_output.setMinimumHeight(180)

        debug_card.addLayout(debug_toolbar)
        debug_card.addWidget(self.debug_output)

        left_layout.addWidget(self.input_card)
        left_layout.addWidget(self.local_card)
        left_layout.addWidget(self.summary_lang_card)
        left_layout.addWidget(action_card)
        left_layout.addWidget(debug_card, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.progress_card = SectionCard(self.ui.progress_title)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setMinimumHeight(30)

        self.status = QLabel(self.ui.idle)
        self.status.setObjectName("statusLabel")
        self.status.setWordWrap(True)

        self.eta_label = QLabel("Elapsed: --:--  |  Remaining: --:--")
        self.eta_label.setObjectName("envLabel")
        self.eta_label.setWordWrap(True)

        self.progress_card.addWidget(self.progress)
        self.progress_card.addWidget(self.status)
        self.progress_card.addWidget(self.eta_label)

        self.result_card = SectionCard(self.ui.result_title)

        result_tools = QHBoxLayout()
        self.save_btn = QPushButton(self.ui.save)
        self.copy_btn = QPushButton(self.ui.copy)
        self.open_folder_btn = QPushButton(self.ui.open_folder)

        self.save_btn.setMinimumHeight(38)
        self.copy_btn.setMinimumHeight(38)
        self.open_folder_btn.setMinimumHeight(38)

        result_tools.addWidget(self.save_btn)
        result_tools.addWidget(self.copy_btn)
        result_tools.addWidget(self.open_folder_btn)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(500)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.result_card.addLayout(result_tools)
        self.result_card.addWidget(self.output)

        right_layout.addWidget(self.progress_card)
        right_layout.addWidget(self.result_card, 1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([620, 820])

        root.addWidget(splitter, 1)

        self.start_btn.clicked.connect(self.start)
        self.pause_btn.clicked.connect(self.pause)
        self.resume_btn.clicked.connect(self.resume)
        self.stop_btn.clicked.connect(self.stop)
        self.save_btn.clicked.connect(self.save_result_as)
        self.copy_btn.clicked.connect(self.copy_result)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.add_files_btn.clicked.connect(self.add_local_files)
        self.clear_files_btn.clicked.connect(self.clear_local_files)
        self.clear_debug_btn.clicked.connect(self.clear_debug_log)
        self.show_debug_checkbox.toggled.connect(self.on_toggle_debug_panel)

        self.paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        self.paste_shortcut.activated.connect(self.focus_input_for_paste)

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
                font-size: 15px;
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
                min-width: 110px;
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
            }

            QProgressBar::chunk {
                background-color: #08b625;
                border-radius: 7px;
            }
        """)

    def debug_log(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {text}"
        print(line)
        if self.show_debug_checkbox.isChecked():
            self.debug_output.append(line)
            self.debug_output.moveCursor(QTextCursor.End)

    def clear_debug_log(self):
        self.debug_output.clear()

    def on_toggle_debug_panel(self, checked: bool):
        self.debug_output.setVisible(checked)
        self.clear_debug_btn.setVisible(checked)

    def _format_seconds(self, seconds: float) -> str:
        seconds = max(0, int(seconds))
        mm, ss = divmod(seconds, 60)
        hh, mm = divmod(mm, 60)
        if hh > 0:
            return f"{hh:02d}:{mm:02d}:{ss:02d}"
        return f"{mm:02d}:{ss:02d}"

    def current_elapsed_text(self) -> str:
        if not self.task_start_ts:
            return "--:--"
        return self._format_seconds(time.time() - self.task_start_ts)

    def _parse_status_text(self, text: str):
        text = (text or "").strip()
        m = self.TASK_PREFIX_RE.match(text)
        if not m:
            return None, None, text
        try:
            idx = int(m.group(1))
            total = int(m.group(2))
        except Exception:
            idx, total = None, None
        stage = m.group(3).strip()
        return idx, total, stage

    def _reset_progress_for_new_scope(self, task_index, task_total, stage_name):
        self.current_task_index = task_index
        self.current_task_total = task_total
        self.current_stage_name = stage_name or ""
        self.last_progress_value = 0
        self.progress.setValue(0)

    def on_status_update(self, text: str):
        self.current_status_text = text
        self.status.setText(text)

        task_index, task_total, stage_name = self._parse_status_text(text)

        if task_index is None:
            return

        task_changed = (self.current_task_index != task_index) or (self.current_task_total != task_total)
        stage_changed = (self.current_stage_name != (stage_name or ""))

        if task_changed:
            self._reset_progress_for_new_scope(task_index, task_total, stage_name)
            return

        if stage_changed:
            self.current_stage_name = stage_name or ""

            stage_lower = (stage_name or "").lower()
            current_val = self.progress.value()

            if "downloading" in stage_lower:
                target = 0
            elif "transcribing" in stage_lower:
                target = max(current_val, 0)
            elif "summarizing" in stage_lower:
                target = max(current_val, 85)
            else:
                target = current_val

            self.last_progress_value = max(self.last_progress_value, target)
            self.progress.setValue(self.last_progress_value)

    def on_progress_update(self, value: int):
        if not self.is_running:
            self.progress.setValue(value)
            self.last_progress_value = value
            return

        incoming = max(0, min(100, int(value)))

        if incoming < self.last_progress_value:
            return

        self.last_progress_value = incoming
        self.progress.setValue(incoming)
        self.update_eta_display()

    def reset_eta_display(self):
        self.task_start_ts = None
        self.last_progress_value = 0
        self.current_task_index = None
        self.current_task_total = None
        self.current_stage_name = ""
        self.current_status_text = self.ui.idle
        self.eta_label.setText("Elapsed: --:--  |  Remaining: --:--")

    def update_eta_display(self):
        if not self.is_running or not self.task_start_ts:
            return

        elapsed = time.time() - self.task_start_ts
        progress = max(0, min(100, self.last_progress_value))

        if progress <= 0 or elapsed <= 0:
            self.eta_label.setText(
                f"Elapsed: {self._format_seconds(elapsed)}  |  Remaining: --:--"
            )
            return

        rate = progress / elapsed
        if rate <= 0:
            remaining_text = "--:--"
        else:
            remaining = max(0.0, (100 - progress) / rate)
            remaining_text = self._format_seconds(remaining)

        self.eta_label.setText(
            f"Elapsed: {self._format_seconds(elapsed)}  |  Remaining: {remaining_text}"
        )

    def _after_ui_ready(self):
        self.progress.setValue(0)
        self.output.clear()
        self.last_result_text = ""
        self.last_export_payload = None
        self.control_flag["stop"] = False
        self.control_flag["pause"] = False
        self.refresh_local_files_display()
        self._set_running_state(False)
        self.status.setText(self.ui.idle)
        self.ffmpeg_label.setText(self.ui.env_checking)
        self.reset_eta_display()
        self.debug_log("UI READY")
        QTimer.singleShot(250, self.start_environment_check)

    def start_environment_check(self):
        if self.env_check_running:
            return

        self.env_check_running = True
        self.ffmpeg_label.setText(self.ui.env_checking)
        self.debug_log("ENVIRONMENT CHECK START")

        worker = EnvironmentCheckWorker()
        worker.signals.finished.connect(self.on_environment_check_finished)
        worker.signals.failed.connect(self.on_environment_check_failed)
        self.pool.start(worker)

    def on_environment_check_finished(self, payload: dict):
        self.env_check_running = False

        ffmpeg_info = payload["ffmpeg_info"]
        whisper_info = payload["whisper_info"]

        lines = []

        if ffmpeg_info["installed"]:
            lines.append(f"✅ {self.ui.ffmpeg_found}")
            lines.append(f"{self.ui.ffmpeg_path}: {ffmpeg_info['ffmpeg_path']}")
        else:
            lines.append(f"⚠️ {self.ui.ffmpeg_missing}")

        if whisper_info["faster_whisper_installed"]:
            lines.append("✅ faster-whisper: installed")
        else:
            lines.append("❌ faster-whisper: not installed")

        if whisper_info["ctranslate2_installed"]:
            lines.append("✅ ctranslate2: installed")
        else:
            lines.append("⚠️ ctranslate2: not detected or failed")

        if whisper_info["preferred_model_dir"]:
            lines.append(f"✅ Local model: {whisper_info['preferred_model_dir']}")
        else:
            lines.append("⚠️ Local model: not found (transcription may fail if offline)")

        lines.append(f"Offline mode: {'ON' if whisper_info['offline_mode'] else 'OFF'}")
        lines.append(f"GPU transcribe: {'READY' if whisper_info.get('cuda_ready') else 'FAIL'}")

        if whisper_info.get("cuda_reason"):
            lines.append(f"GPU detail: {whisper_info['cuda_reason']}")

        self.ffmpeg_label.setText("\n".join(lines))
        self.debug_log("ENVIRONMENT CHECK DONE")

    def on_environment_check_failed(self, message: str):
        self.env_check_running = False
        self.ffmpeg_label.setText(f"⚠️ {message}")
        self.debug_log(f"ENVIRONMENT CHECK ERROR: {message}")

    def refresh_local_files_display(self):
        self.local_files_info.setText(f"{self.ui.local_file_count}: {len(self.local_files)}")
        self.local_files_box.setPlainText("\n".join(self.local_files))

    def _set_running_state(self, running: bool):
        self.is_running = running
        self.start_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running and not self.control_flag.get("pause"))
        self.resume_btn.setEnabled(running and self.control_flag.get("pause"))
        self.stop_btn.setEnabled(running)

        self.add_files_btn.setEnabled(not running)
        self.clear_files_btn.setEnabled(not running)
        self.summary_lang_combo.setEnabled(not running)
        self.input.setReadOnly(running)

    def focus_input_for_paste(self):
        if not self.is_running:
            self.input.setFocus()
            self.input.paste()
            self.debug_log("PASTE INTO URL INPUT")

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
        new_count = 0
        for f in files:
            if f not in existing:
                self.local_files.append(f)
                existing.add(f)
                new_count += 1

        self.refresh_local_files_display()
        self.status.setText(self.ui.idle)
        self.debug_log(f"LOCAL FILES ADDED: {new_count}")

    def clear_local_files(self):
        self.local_files = []
        self.refresh_local_files_display()
        self.status.setText(self.ui.idle)
        self.debug_log("LOCAL FILE LIST CLEARED")

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
        self.debug_log("START CLICKED")

        if self.is_running:
            self.debug_log("START IGNORED: already running")
            return

        tasks = self.build_tasks()
        self.debug_log(f"TASK COUNT: {len(tasks)}")

        if not tasks:
            self.on_status_update(f"❌ {self.ui.please_input}")
            self.debug_log("NO TASK TO RUN")
            return

        self.output.clear()
        self.last_result_text = ""
        self.last_export_payload = None
        self.progress.setValue(0)
        self.control_flag["stop"] = False
        self.control_flag["pause"] = False
        self.last_run_had_error = False
        self.on_status_update(self.ui.preparing)

        summary_language = self.summary_lang_combo.currentData()
        self.debug_log(f"SUMMARY LANGUAGE: {summary_language}")

        self.task_start_ts = time.time()
        self.last_progress_value = 0
        self.current_task_index = None
        self.current_task_total = None
        self.current_stage_name = ""
        self.update_eta_display()
        self.eta_timer.start(1000)

        worker = Worker(tasks, self.control_flag, self.ui, summary_language)
        self.current_worker = worker

        worker.signals.progress.connect(self.on_progress_update)
        worker.signals.status.connect(self.on_status_update)
        worker.signals.result.connect(self.append_result)
        worker.signals.finished.connect(self.on_worker_finished)
        worker.signals.failed.connect(self.on_worker_failed)
        worker.signals.debug.connect(self.debug_log)

        self._set_running_state(True)
        self.pool.start(worker)

    def pause(self):
        if not self.is_running:
            return
        if self.control_flag.get("pause"):
            return

        self.control_flag["pause"] = True
        self.on_status_update(self.ui.pausing)
        self.debug_log("PAUSE CLICKED")
        self._set_running_state(True)

    def resume(self):
        if not self.is_running:
            return
        if not self.control_flag.get("pause"):
            return

        self.control_flag["pause"] = False
        self.on_status_update(self.ui.resuming)
        self.debug_log("RESUME CLICKED")
        self._set_running_state(True)

    def stop(self):
        if not self.is_running:
            return
        self.control_flag["stop"] = True
        self.control_flag["pause"] = False
        self.on_status_update(self.ui.stopping)
        self.eta_timer.stop()
        self.debug_log("STOP CLICKED")
        self._set_running_state(True)

    def on_worker_failed(self, message: str):
        self.last_run_had_error = True
        self.debug_log(f"WORKER FAILED SIGNAL: {message}")
        pretty = self.ui.build_transcribe_error_message(message)
        QMessageBox.warning(self, self.ui.error, pretty)

    def on_worker_finished(self, success: bool):
        self.debug_log("WORKER FINISHED")
        self.current_worker = None
        self.eta_timer.stop()
        elapsed_text = self.current_elapsed_text()
        self._set_running_state(False)

        if self.control_flag["stop"]:
            self.on_status_update(self.ui.stopped)
            self.eta_label.setText(f"Elapsed: {elapsed_text}  |  Remaining: 00:00")
        else:
            if success and not self.last_run_had_error:
                if self.progress.value() < 100:
                    self.progress.setValue(100)
                self.last_progress_value = 100
                self.on_status_update(f"{self.ui.done} · {self.ui.ready_for_new_input}")
            else:
                self.on_status_update(f"{self.ui.done_with_error} · {self.ui.ready_for_new_input}")

            self.eta_label.setText(f"Elapsed: {elapsed_text}  |  Remaining: 00:00")

        self.control_flag["stop"] = False
        self.control_flag["pause"] = False
        self._set_running_state(False)

    def append_result(self, text: str):
        if self.last_result_text:
            self.last_result_text += "\n" + text
        else:
            self.last_result_text = text

        self.output.append(text)
        self.output.moveCursor(QTextCursor.End)
        self.debug_log("RESULT APPENDED TO UI")

    def _derive_export_title(self) -> str:
        text = self.last_result_text.strip()
        if not text:
            return "result"

        first_line = text.splitlines()[0].strip()
        m = re.match(r"^===\s*(.*?)\s*===$", first_line)
        if m:
            return m.group(1).strip() or "result"
        return "result"

    def save_result_as(self):
        if not self.last_result_text.strip():
            QMessageBox.information(self, self.ui.window_title, self.ui.no_result)
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.ui.save_dialog_title,
            f"{self._derive_export_title()}.txt",
            self.ui.save_filter,
        )

        if not file_path:
            return

        payload = self.last_export_payload
        if payload is None:
            payload = build_export_payload(
                title=self._derive_export_title(),
                transcript="",
                summary="",
                metadata={},
                raw_text=self.last_result_text,
            )

        try:
            export_by_extension(file_path, payload)
        except Exception as e:
            QMessageBox.warning(self, self.ui.error, str(e))
            self.debug_log(f"RESULT SAVE ERROR: {e}")
            return

        QMessageBox.information(self, self.ui.window_title, f"{self.ui.saved_ok}\n{file_path}")
        self.debug_log(f"RESULT SAVED AS: {file_path}")

    def copy_result(self):
        if not self.last_result_text.strip():
            QMessageBox.information(self, self.ui.window_title, self.ui.no_result)
            return

        QApplication.clipboard().setText(self.last_result_text)
        self.on_status_update(self.ui.copy_ok)
        self.debug_log("RESULT COPIED TO CLIPBOARD")

    def open_output_folder(self):
        from pipeline.knowledge import get_output_dir

        output_dir = get_output_dir()

        try:
            os.startfile(output_dir)
            self.debug_log(f"OPEN OUTPUT FOLDER: {output_dir}")
        except Exception as e:
            QMessageBox.warning(self, self.ui.error, f"{self.ui.open_folder_fail}\n{e}")
            self.debug_log(f"OPEN OUTPUT FOLDER ERROR: {e}")
