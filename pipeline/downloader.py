import os
import re
import time
import shutil
import tempfile
from typing import Callable, Dict, Optional, Tuple, List

from pipeline.cleaner import to_traditional_chinese
from pipeline.ffmpeg_utils import get_ffmpeg_info

try:
    import yt_dlp
except Exception:
    yt_dlp = None


# =========================================================
# Path / basic helpers
# =========================================================

def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _tmp_dir() -> str:
    path = os.path.join(_project_root(), "data", "tmp")
    os.makedirs(path, exist_ok=True)
    return path


def _dbg(message: str):
    print(f"[download] {message}")


def _is_stopped(control_flag) -> bool:
    return bool(control_flag and control_flag.get("stop"))


def _raise_if_stopped(control_flag):
    if _is_stopped(control_flag):
        raise RuntimeError("Download stopped by user.")


def _safe_progress_emit(progress_callback: Optional[Callable[[int], None]], value: int):
    if progress_callback:
        try:
            progress_callback(int(max(0, min(100, value))))
        except Exception:
            pass


def _normalize_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return "Untitled"
    title = to_traditional_chinese(title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or "Untitled"


def _safe_filename(name: str, max_len: int = 120) -> str:
    name = _normalize_title(name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.replace("：", "_").replace("／", "_").replace("｜", "_")
    name = re.sub(r"_+", "_", name)
    name = re.sub(r"\s*_\s*", "_", name)
    name = name.strip(" ._-")
    if not name:
        name = "Untitled"
    if len(name) > max_len:
        name = name[:max_len].rstrip(" ._-")
    return name or "Untitled"


def _guess_is_music_like(title: str, description: str = "") -> bool:
    sample = f"{title}\n{description}".lower()
    keywords = [
        "lyrics", "lyric", "mv", "music video", "official audio", "official music video",
        "cover", "karaoke", "song", "album", "remix", "ost", "歌詞", "音樂", "歌曲", "翻唱",
    ]
    return any(k in sample for k in keywords)


def _require_ytdlp():
    if yt_dlp is None:
        raise RuntimeError(
            "yt-dlp is not installed. Please run:\n"
            "pip install yt-dlp"
        )


# =========================================================
# Subtitle handling
# =========================================================

def _subtitle_lang_candidates() -> Tuple[str, ...]:
    return (
        "zh-TW",
        "zh-Hant",
        "zh-HK",
        "zh",
        "zh-CN",
        "zh-Hans",
        "en",
        "en-US",
        "ja",
    )


def _read_text_file(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""

    encodings = ["utf-8", "utf-8-sig", "cp950", "big5", "latin-1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, errors="ignore") as f:
                return f.read()
        except Exception:
            continue
    return ""


def _clean_subtitle_text(text: str) -> str:
    text = text or ""
    text = text.replace("\ufeff", "")
    lines = text.splitlines()
    out = []

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if s.upper() == "WEBVTT":
            continue

        if "-->" in s:
            continue

        if re.fullmatch(r"\d+", s):
            continue

        s = re.sub(r"<[^>]+>", "", s).strip()
        if not s:
            continue

        out.append(s)

    dedup = []
    prev = None
    for line in out:
        norm = re.sub(r"\s+", "", line)
        if norm == prev:
            continue
        dedup.append(line)
        prev = norm

    return "\n".join(dedup).strip()


def _find_subtitle_file(base_dir: str, stem: str) -> Tuple[str, str]:
    """
    回傳 (path, source)
    source: manual / auto / ""
    """
    if not os.path.isdir(base_dir):
        return "", ""

    files = os.listdir(base_dir)

    manual_patterns = []
    auto_patterns = []

    for lang in _subtitle_lang_candidates():
        manual_patterns.extend([
            f"{stem}.{lang}.vtt",
            f"{stem}.{lang}.srt",
            f"{stem}.{lang}.ass",
        ])
        auto_patterns.extend([
            f"{stem}.{lang}.vtt",
            f"{stem}.{lang}.srt",
            f"{stem}.{lang}.ass",
        ])

    for name in manual_patterns:
        full = os.path.join(base_dir, name)
        if os.path.exists(full):
            return full, "manual"

    for name in auto_patterns:
        full = os.path.join(base_dir, name)
        if os.path.exists(full):
            return full, "auto"

    for fn in files:
        lower = fn.lower()
        if lower.startswith(stem.lower()) and lower.endswith((".vtt", ".srt", ".ass")):
            return os.path.join(base_dir, fn), "auto"

    return "", ""


def _is_subtitle_rate_limit_error(err_text: str) -> bool:
    t = (err_text or "").lower()
    return (
        "unable to download video subtitles" in t
        or "http error 429" in t
        or "too many requests" in t
        or "subtitle" in t and "403" in t
        or "subtitle" in t and "timeout" in t
    )


# =========================================================
# yt-dlp metadata / options
# =========================================================

def _extract_basic_info(url: str) -> Dict[str, str]:
    _require_ytdlp()

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 25,
        "retries": 2,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        },
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        "id": info.get("id") or "",
        "title": _normalize_title(info.get("title") or "Untitled"),
        "description": info.get("description") or "",
        "webpage_url": info.get("webpage_url") or url,
    }


def _detect_ffmpeg() -> Dict:
    try:
        return get_ffmpeg_info()
    except Exception:
        return {
            "installed": False,
            "ffmpeg_path": "",
            "ffprobe_path": "",
            "version": "",
            "error": "ffmpeg check failed",
        }


def _download_hook_factory(progress_callback: Optional[Callable[[int], None]], control_flag):
    def hook(d):
        _raise_if_stopped(control_flag)

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            if total > 0:
                pct = int(downloaded / total * 55)
            else:
                pct = 10
            _safe_progress_emit(progress_callback, pct)
        elif status == "finished":
            _safe_progress_emit(progress_callback, 60)
    return hook


def _build_download_opts(
    tmp_dir: str,
    progress_callback,
    control_flag,
    with_subtitles: bool,
) -> Dict:
    ffmpeg_info = _detect_ffmpeg()
    ffmpeg_installed = bool(ffmpeg_info.get("installed"))
    ffmpeg_path = ffmpeg_info.get("ffmpeg_path", "") or ""
    ffmpeg_dir = os.path.dirname(ffmpeg_path) if ffmpeg_path else ""

    opts = {
        "format": "bestaudio/best",
        "paths": {"home": tmp_dir},
        "outtmpl": "%(title).120B__%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 8,
        "file_access_retries": 3,
        "extractor_retries": 3,
        "socket_timeout": 40,
        "concurrent_fragment_downloads": 1,
        "skip_unavailable_fragments": True,
        "overwrites": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        },
        "progress_hooks": [_download_hook_factory(progress_callback, control_flag)],
    }

    if with_subtitles:
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = list(_subtitle_lang_candidates())
        opts["subtitlesformat"] = "vtt/srt/best"
    else:
        opts["writesubtitles"] = False
        opts["writeautomaticsub"] = False

    if ffmpeg_installed and ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
        _dbg(f"ffmpeg detected, enable postprocess: {ffmpeg_dir}")
    else:
        _dbg("ffmpeg not found, skip postprocess and keep original audio container")

    return opts


# =========================================================
# Download execution
# =========================================================

def _find_downloaded_audio_file(tmp_dir: str, video_id: str) -> str:
    if not os.path.isdir(tmp_dir):
        return ""

    audio_exts = (".mp3", ".m4a", ".webm", ".opus", ".wav", ".aac", ".ogg", ".mp4")
    candidates = []

    for fn in os.listdir(tmp_dir):
        full = os.path.join(tmp_dir, fn)
        if not os.path.isfile(full):
            continue
        lower = fn.lower()
        if video_id and f"__{video_id}." in lower and lower.endswith(audio_exts):
            candidates.append(full)

    if candidates:
        candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return candidates[0]

    for fn in sorted(os.listdir(tmp_dir), key=lambda x: os.path.getmtime(os.path.join(tmp_dir, x)), reverse=True):
        full = os.path.join(tmp_dir, fn)
        if os.path.isfile(full) and fn.lower().endswith(audio_exts):
            return full

    return ""


def _download_once(
    url: str,
    progress_callback=None,
    control_flag=None,
    with_subtitles: bool = True,
) -> Dict[str, str]:
    _require_ytdlp()
    _raise_if_stopped(control_flag)

    info = _extract_basic_info(url)
    video_id = info["id"]
    title = info["title"]
    description = info["description"]

    tmp_dir = tempfile.mkdtemp(prefix="media2txt_", dir=_tmp_dir())
    opts = _build_download_opts(tmp_dir, progress_callback, control_flag, with_subtitles=with_subtitles)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            _raise_if_stopped(control_flag)
            ydl.extract_info(url, download=True)

        _safe_progress_emit(progress_callback, 62)

        audio_path = _find_downloaded_audio_file(tmp_dir, video_id)
        if not audio_path:
            raise RuntimeError("yt-dlp finished but no downloaded audio file was found.")

        stem = os.path.splitext(os.path.basename(audio_path))[0]
        subtitle_path, subtitle_source = ("", "")
        subtitle_text = ""

        if with_subtitles:
            subtitle_path, subtitle_source = _find_subtitle_file(tmp_dir, stem)
            subtitle_text = _clean_subtitle_text(_read_text_file(subtitle_path)) if subtitle_path else ""

        _safe_progress_emit(progress_callback, 65)

        return {
            "audio_path": audio_path,
            "title": title,
            "video_id": video_id,
            "subtitle_text": subtitle_text,
            "subtitle_source": subtitle_source,
            "is_music_like": _guess_is_music_like(title, description),
            "tmp_dir": tmp_dir,
            "used_subtitle_mode": "with_subtitles" if with_subtitles else "audio_only",
        }
    except Exception:
        raise


def _move_result_to_final_location(result: Dict[str, str], progress_callback=None, control_flag=None) -> Dict[str, str]:
    _raise_if_stopped(control_flag)

    final_dir = _tmp_dir()
    ext = os.path.splitext(result["audio_path"])[1]
    final_name = f"{_safe_filename(result['title'])}__{result['video_id']}{ext}"
    final_audio_path = os.path.join(final_dir, final_name)

    if os.path.abspath(result["audio_path"]) != os.path.abspath(final_audio_path):
        if os.path.exists(final_audio_path):
            try:
                os.remove(final_audio_path)
            except Exception:
                pass
        shutil.move(result["audio_path"], final_audio_path)

    try:
        shutil.rmtree(result["tmp_dir"], ignore_errors=True)
    except Exception:
        pass

    _safe_progress_emit(progress_callback, 65)

    return {
        "audio_path": final_audio_path,
        "title": result["title"],
        "video_id": result["video_id"],
        "subtitle_text": result["subtitle_text"],
        "subtitle_source": result["subtitle_source"],
        "is_music_like": result["is_music_like"],
    }


def download_audio(url: str, progress_callback=None, control_flag=None) -> Dict[str, str]:
    """
    相容目前 worker 呼叫介面。

    這版重點修正：
    1. 字幕 429 / 403 / timeout / subtitle fetch fail -> 自動 fallback 到 audio-only
    2. 不再把字幕失敗當成整支影片下載失敗
    """
    _require_ytdlp()

    url = (url or "").strip()
    if not url:
        raise RuntimeError("Empty YouTube URL.")

    _raise_if_stopped(control_flag)
    _safe_progress_emit(progress_callback, 1)

    attempts = 3
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            _dbg(f"Attempt {attempt}/{attempts}: {url}")

            # 第一階段：先嘗試含字幕
            try:
                result = _download_once(
                    url,
                    progress_callback=progress_callback,
                    control_flag=control_flag,
                    with_subtitles=True,
                )
                return _move_result_to_final_location(result, progress_callback, control_flag)

            except Exception as e_sub:
                err_text = str(e_sub)
                _dbg(f"Subtitles-enabled attempt failed: {err_text}")

                # 若是字幕下載被限流 / 被擋 / 超時，就降級成 audio-only
                if _is_subtitle_rate_limit_error(err_text):
                    _dbg("subtitle unavailable or rate-limited, fallback to audio-only download")
                    result = _download_once(
                        url,
                        progress_callback=progress_callback,
                        control_flag=control_flag,
                        with_subtitles=False,
                    )
                    return _move_result_to_final_location(result, progress_callback, control_flag)

                # 不是字幕錯誤，往外丟給外層 retry
                raise

        except Exception as e:
            last_error = e
            _dbg(f"Got error: {e}")
            _raise_if_stopped(control_flag)

            if attempt < attempts:
                time.sleep(2.0 * attempt)
                continue

    raise RuntimeError(f"Failed to download YouTube media after {attempts} attempts. detail={last_error}")


# =========================================================
# Local file path passthrough
# =========================================================

def process_local_media(local_path: str) -> Dict[str, str]:
    local_path = os.path.abspath((local_path or "").strip())
    if not local_path:
        raise RuntimeError("Empty local media path.")
    if not os.path.exists(local_path):
        raise RuntimeError(f"Local media file not found: {local_path}")

    base = os.path.basename(local_path)
    stem, _ext = os.path.splitext(base)

    title = _normalize_title(stem)
    video_id = _safe_filename(stem, max_len=48)

    return {
        "audio_path": local_path,
        "title": title,
        "video_id": video_id,
        "subtitle_text": "",
        "subtitle_source": "",
        "is_music_like": _guess_is_music_like(title, ""),
    }
