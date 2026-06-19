import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any

from pipeline.exporter import build_export_payload, export_note


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(BASE_DIR, "knowledge")
META_DIR = os.path.join(OUTPUT_DIR, "_meta")


def ensure_output_dir() -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(META_DIR, exist_ok=True)
    return OUTPUT_DIR


def get_output_dir() -> str:
    return ensure_output_dir()


def get_meta_dir() -> str:
    ensure_output_dir()
    return META_DIR


def _normalize_whitespace(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _safe_filename(name: str, max_len: int = 120) -> str:
    name = _normalize_whitespace(name)

    if not name:
        name = "untitled"

    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.replace("⧸", "_")
    name = name.replace("／", "_")
    name = name.replace("？", "_")
    name = name.replace("！", "!")
    name = name.replace("：", "_")
    name = name.replace("，", ",")
    name = name.replace("。", ".")
    name = re.sub(r"_+", "_", name)
    name = re.sub(r"\s*_\s*", "_", name)
    name = name.strip(" ._-\t\r\n")

    if not name:
        name = "untitled"

    if len(name) > max_len:
        name = name[:max_len].rstrip(" ._-")

    if not name:
        name = "untitled"

    return name


def _build_output_basename(title: str, timestamp: Optional[str] = None) -> str:
    safe_title = _safe_filename(title or "untitled")
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe_title}_{ts}"


def _metadata_sidecar_path(main_path: str) -> str:
    base_name = os.path.splitext(os.path.basename(main_path))[0]
    return os.path.join(get_meta_dir(), f"{base_name}.meta.json")


def _write_metadata_sidecar(main_path: str, metadata: Dict[str, Any]):
    sidecar = _metadata_sidecar_path(main_path)
    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def save_note(
    title: str,
    content: str,
    video_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    export_format: Optional[str] = None,
    transcript: Optional[str] = None,
    summary: Optional[str] = None,
) -> str:
    """
    向下相容舊呼叫：
        save_note(title, content, video_id=...)

    新版功能：
        - 主檔輸出到 knowledge/
        - metadata sidecar 輸出到 knowledge/_meta/
        - 可指定 export_format: txt / md / json / docx
        - 可帶 transcript / summary 做結構化輸出
    """
    out_dir = ensure_output_dir()

    fmt = (export_format or os.environ.get("MEDIA2TXT_EXPORT_FORMAT", "txt")).strip().lower()
    if fmt not in ("txt", "md", "json", "docx"):
        fmt = "txt"

    meta = dict(metadata or {})
    if video_id and "video_id" not in meta:
        meta["video_id"] = video_id
    if "saved_at" not in meta:
        meta["saved_at"] = datetime.now().isoformat(timespec="seconds")

    payload = build_export_payload(
        title=title,
        transcript=transcript or "",
        summary=summary or "",
        metadata=meta,
        raw_text=content or "",
    )

    basename = _build_output_basename(title=title)
    path = os.path.join(out_dir, f"{basename}.{fmt}")

    final_path = export_note(path, payload)

    if meta:
        sidecar_meta = dict(meta)
        sidecar_meta["main_file"] = os.path.abspath(final_path)
        sidecar_meta["main_file_name"] = os.path.basename(final_path)
        sidecar_meta["main_file_ext"] = os.path.splitext(final_path)[1].lower()
        _write_metadata_sidecar(final_path, sidecar_meta)

    return final_path
