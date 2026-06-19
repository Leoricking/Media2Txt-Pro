import shutil
import subprocess
from typing import Dict


def get_ffmpeg_info() -> Dict[str, str | bool]:
    ffmpeg_path = shutil.which("ffmpeg")
    installed = bool(ffmpeg_path)
    version = ""

    if installed:
        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            )
            first_line = (result.stdout or "").splitlines()
            if first_line:
                version = first_line[0].strip()
        except Exception:
            version = ""

    return {
        "installed": installed,
        "ffmpeg_path": ffmpeg_path or "",
        "version": version,
    }
