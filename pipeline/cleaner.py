import re

try:
    from opencc import OpenCC
    _OPENCC = OpenCC("s2t")
except Exception:
    _OPENCC = None


ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
MULTI_BLANK_RE = re.compile(r"\n{3,}")
VTT_TIMESTAMP_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}.*$"
)
WEBVTT_HEADER_RE = re.compile(r"^WEBVTT", re.IGNORECASE)
CUE_INDEX_RE = re.compile(r"^\d+$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MUSIC_LIKE_TITLE_RE = re.compile(
    r"(lyric|lyrics|official lyric|mv|music video|audio|歌詞|中字|lyrics video|official audio)",
    re.IGNORECASE,
)


def strip_ansi(text: str) -> str:
    if not text:
        return ""
    return ANSI_ESCAPE_RE.sub("", text)


def to_traditional_chinese(text: str) -> str:
    """
    若系統有 opencc，就把簡體中文統一轉為繁體中文。
    其他語言內容保持原樣。
    """
    if not text:
        return ""

    if _OPENCC is None:
        return text

    try:
        return _OPENCC.convert(text)
    except Exception:
        return text


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = strip_ansi(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = text.strip()
    text = MULTI_BLANK_RE.sub("\n\n", text)
    return text


def clean_transcript(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = to_traditional_chinese(text)
    return text.strip()


def clean_summary(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = to_traditional_chinese(text)
    return text.strip()


def parse_vtt_to_text(vtt_text: str) -> str:
    if not vtt_text:
        return ""

    lines = normalize_text(vtt_text).split("\n")
    result = []
    seen_recent = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue
        if WEBVTT_HEADER_RE.match(line):
            continue
        if VTT_TIMESTAMP_RE.match(line):
            continue
        if CUE_INDEX_RE.match(line):
            continue

        line = HTML_TAG_RE.sub("", line)
        line = line.replace("&nbsp;", " ")
        line = line.replace("&amp;", "&")
        line = line.replace("&quot;", '"')
        line = line.replace("&#39;", "'")
        line = line.strip()

        if not line:
            continue

        if seen_recent and line == seen_recent[-1]:
            continue

        result.append(line)
        seen_recent.append(line)
        if len(seen_recent) > 5:
            seen_recent.pop(0)

    return clean_transcript("\n".join(result))


def transcript_quality_score(text: str) -> dict:
    cleaned = clean_transcript(text)
    lines = [x.strip() for x in cleaned.split("\n") if x.strip()]
    words = cleaned.split()

    return {
        "char_count": len(cleaned),
        "line_count": len(lines),
        "word_count": len(words),
    }


def looks_too_short(text: str) -> bool:
    score = transcript_quality_score(text)
    return score["char_count"] < 120 or score["line_count"] < 8 or score["word_count"] < 20


def looks_music_like_title(title: str) -> bool:
    if not title:
        return False
    return bool(MUSIC_LIKE_TITLE_RE.search(title))