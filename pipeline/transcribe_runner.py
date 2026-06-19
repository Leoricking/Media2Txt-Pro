"""Isolated faster-whisper child process runner.

This module intentionally contains no Qt imports.  Native CUDA/CTranslate2 crashes
terminate only this child, allowing the parent GUI to retry on CPU.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


def _emit(event_type: str, **payload) -> None:
    data = {"type": event_type, **payload}
    print(json.dumps(data, ensure_ascii=False), flush=True)


def _write_text(path: str, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m pipeline.transcribe_runner <request.json>", file=sys.stderr)
        return 2

    request_path = Path(sys.argv[1])
    request = json.loads(request_path.read_text(encoding="utf-8"))

    audio_path = str(request["audio_path"])
    device = str(request.get("device", "cpu"))
    is_music_like = bool(request.get("is_music_like", False))
    result_path = str(request["result_path"])
    error_path = str(request["error_path"])

    # Must be set before importing pipeline.transcriber because it reads env at import.
    os.environ["MEDIA2TXT_TRANSCRIBE_CHILD"] = "1"
    os.environ["MEDIA2TXT_TRANSCRIBE_SUBPROCESS"] = "0"
    os.environ["WHISPER_DEVICE"] = device

    try:
        from pipeline.transcriber import _transcribe_in_process

        _emit("debug", message=f"runner started device={device}")
        result = _transcribe_in_process(
            audio_path=audio_path,
            progress_callback=lambda value: _emit("progress", value=int(value)),
            stop_flag={"stop": False, "pause": False},
            is_music_like=is_music_like,
            debug_callback=lambda message: _emit("debug", message=str(message)),
        )
        if not result.strip():
            raise RuntimeError("Transcription returned empty text")
        _write_text(result_path, result)
        _emit("debug", message=f"runner completed device={device}")
        return 0
    except Exception:
        error = traceback.format_exc()
        _write_text(error_path, error)
        _emit("error", message=error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
