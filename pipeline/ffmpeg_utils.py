import os
import shutil
from pathlib import Path


def find_ffmpeg_executable() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe and os.path.exists(exe):
        return os.path.abspath(exe)

    project_root = Path.cwd()
    candidates = [
        project_root / "ffmpeg.exe",
        project_root / "ffmpeg" / "bin" / "ffmpeg.exe",
        project_root / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())

    return None


def find_ffprobe_executable(ffmpeg_path: str | None) -> str | None:
    if ffmpeg_path:
        ffmpeg_file = Path(ffmpeg_path)
        ffprobe_same_dir = ffmpeg_file.with_name("ffprobe.exe")
        if ffprobe_same_dir.exists():
            return str(ffprobe_same_dir.resolve())

    exe = shutil.which("ffprobe")
    if exe and os.path.exists(exe):
        return os.path.abspath(exe)

    return None


def get_ffmpeg_info() -> dict:
    ffmpeg_path = find_ffmpeg_executable()
    ffprobe_path = find_ffprobe_executable(ffmpeg_path)

    return {
        "installed": ffmpeg_path is not None,
        "ffmpeg_path": ffmpeg_path,
        "ffprobe_path": ffprobe_path,
    }