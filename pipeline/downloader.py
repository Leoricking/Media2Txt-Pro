import glob
import os
import shutil
from pathlib import Path

from pipeline.ffmpeg_utils import get_ffmpeg_info
from pipeline.cleaner import parse_vtt_to_text, looks_music_like_title


COOKIE_FILE_NAME = "cookies.txt"


def _get_cookie_file():
    path = os.path.abspath(COOKIE_FILE_NAME)
    if os.path.exists(path) and os.path.isfile(path):
        return path
    return None


def _get_js_runtimes():
    node_path = shutil.which("node")
    if not node_path:
        return {}
    return {"node": {"path": node_path}}


def _preferred_subtitle_languages():
    return [
        "zh-TW",
        "zh-Hant",
        "zh-HK",
        "zh-CN",
        "zh",
        "en",
        "en-US",
        "en-GB",
        "ko",
        "ja",
    ]


def _find_downloaded_subtitle_file(video_id: str) -> str | None:
    patterns = [
        os.path.join("data", f"{video_id}*.vtt"),
        os.path.join("data", f"{video_id}*.srv3"),
        os.path.join("data", f"{video_id}*.srv2"),
        os.path.join("data", f"{video_id}*.ttml"),
    ]

    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            matches.sort(key=lambda x: len(x))
            return os.path.abspath(matches[0])

    return None


def _read_subtitle_text(subtitle_path: str | None) -> str:
    if not subtitle_path or not os.path.exists(subtitle_path):
        return ""

    try:
        with open(subtitle_path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        return parse_vtt_to_text(raw)
    except Exception:
        return ""


def _build_common_opts(progress_cb, stop_flag):
    def hook(d):
        if stop_flag.get("stop"):
            raise Exception("使用者中止")

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            percent = int(downloaded / total * 100)
            progress_cb(max(0, min(percent, 100)))
        elif status == "finished":
            progress_cb(100)

    ffmpeg_info = get_ffmpeg_info()

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join("data", "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "progress_hooks": [hook],
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 1,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        },
        "js_runtimes": _get_js_runtimes(),
        "remote_components": ["ejs:github"],
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "web_safari"],
            }
        },
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": _preferred_subtitle_languages(),
        "subtitlesformat": "vtt/best",
    }

    cookie_file = _get_cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file

    if ffmpeg_info["installed"]:
        opts["ffmpeg_location"] = ffmpeg_info["ffmpeg_path"]

    return opts, ffmpeg_info


def _extract_info_with_fallback(ydl_opts, url):
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info, ydl
    except yt_dlp.utils.DownloadError as first_error:
        fallback_opts = dict(ydl_opts)
        fallback_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["default"],
            }
        }

        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                return info, ydl
            except Exception:
                raise first_error


def download_audio(url: str, progress_cb, stop_flag) -> dict:
    import yt_dlp

    os.makedirs("data", exist_ok=True)

    ydl_opts, ffmpeg_info = _build_common_opts(progress_cb, stop_flag)
    info, ydl = _extract_info_with_fallback(ydl_opts, url)

    audio_path = ydl.prepare_filename(info)
    video_id = info.get("id") or ""
    title = info.get("title") or info.get("fulltitle") or video_id or "untitled"

    subtitle_path = _find_downloaded_subtitle_file(video_id)
    subtitle_text = _read_subtitle_text(subtitle_path)

    subtitles = info.get("subtitles") or {}
    automatic_captions = info.get("automatic_captions") or {}

    subtitle_source = ""
    if subtitle_text:
        if subtitles:
            subtitle_source = "manual"
        elif automatic_captions:
            subtitle_source = "auto"
        else:
            subtitle_source = "auto"

    categories = info.get("categories") or []
    is_music_like = looks_music_like_title(title) or any(str(x).lower() == "music" for x in categories)

    return {
        "audio_path": audio_path,
        "title": title,
        "video_id": video_id,
        "ffmpeg_installed": ffmpeg_info["installed"],
        "ffmpeg_path": ffmpeg_info["ffmpeg_path"],
        "subtitle_text": subtitle_text,
        "subtitle_source": subtitle_source,
        "is_music_like": is_music_like,
        "media_source": "youtube",
    }


def process_local_media(file_path: str) -> dict:
    abs_path = os.path.abspath(file_path)
    stem = Path(abs_path).stem

    ffmpeg_info = get_ffmpeg_info()
    is_music_like = looks_music_like_title(stem)

    return {
        "audio_path": abs_path,
        "title": stem,
        "video_id": "",
        "ffmpeg_installed": ffmpeg_info["installed"],
        "ffmpeg_path": ffmpeg_info["ffmpeg_path"],
        "subtitle_text": "",
        "subtitle_source": "",
        "is_music_like": is_music_like,
        "media_source": "local",
    }