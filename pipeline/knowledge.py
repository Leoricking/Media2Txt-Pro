import os
import re


INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1F]'
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_filename(name: str) -> str:
    if not name:
        return "untitled"

    name = name.strip()
    name = re.sub(INVALID_FILENAME_CHARS, "_", name)
    name = name.replace("\r", " ").replace("\n", " ")
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(". ")

    if not name:
        name = "untitled"

    if name.upper() in RESERVED_NAMES:
        name = f"_{name}"

    return name[:150]


def build_output_path(title: str, video_id: str = "") -> str:
    os.makedirs("knowledge", exist_ok=True)

    safe_title = sanitize_filename(title)
    base_path = os.path.abspath(os.path.join("knowledge", f"{safe_title}.txt"))

    if not os.path.exists(base_path):
        return base_path

    if video_id:
        alt_path = os.path.abspath(os.path.join("knowledge", f"{safe_title}_({video_id}).txt"))
        if not os.path.exists(alt_path):
            return alt_path

    counter = 2
    while True:
        alt_path = os.path.abspath(os.path.join("knowledge", f"{safe_title}_({counter}).txt"))
        if not os.path.exists(alt_path):
            return alt_path
        counter += 1


def save_note(title: str, text: str, video_id: str = "") -> str:
    os.makedirs("knowledge", exist_ok=True)
    path = build_output_path(title, video_id)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    return path


def get_output_dir() -> str:
    os.makedirs("knowledge", exist_ok=True)
    return os.path.abspath("knowledge")