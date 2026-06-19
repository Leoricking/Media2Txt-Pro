import re
from typing import List


try:
    from opencc import OpenCC
    _opencc = OpenCC("s2t")
except Exception:
    _opencc = None


def to_traditional_chinese(text: str) -> str:
    text = text or ""
    if not text:
        return text
    if _opencc is not None:
        try:
            return _opencc.convert(text)
        except Exception:
            return text
    return text


def _collapse_blank_lines(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_spaces(text: str) -> str:
    text = text or ""
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _normalize_line_for_compare(line: str) -> str:
    line = (line or "").strip().lower()
    line = re.sub(r"\s+", "", line)
    line = re.sub(r"[，,。\.！!？?\-—:：;；「」『』（）()\[\]【】]", "", line)
    return line


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def _is_mostly_noise_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return True

    # 幾乎全是符號 / 無意義片段
    if re.fullmatch(r"[-=~_*•·\.\,\!\?，。！？、/\\|:：;；\[\]\(\)【】]{2,}", s):
        return True

    # 太短又沒什麼資訊
    if len(s) <= 1:
        return True

    # 只有數字或非常碎的字元
    if re.fullmatch(r"[\d\W_]+", s):
        return True

    return False


def _remove_consecutive_duplicate_lines(lines: List[str], max_repeat: int = 1) -> List[str]:
    out = []
    prev_norm = None
    repeat_count = 0

    for line in lines:
        norm = _normalize_line_for_compare(line)
        if not norm:
            continue

        if norm == prev_norm:
            repeat_count += 1
            if repeat_count > max_repeat:
                continue
        else:
            repeat_count = 0
            prev_norm = norm

        out.append(line)

    return out


def _remove_global_near_duplicate_lines(lines: List[str]) -> List[str]:
    """
    移除全域上幾乎完全相同的短句重複，避免影片口播重複洗版。
    但長句不做太激進去重，避免誤刪內容。
    """
    out = []
    seen_short = set()

    for line in lines:
        norm = _normalize_line_for_compare(line)
        if not norm:
            continue

        if len(norm) <= 18:
            if norm in seen_short:
                continue
            seen_short.add(norm)

        out.append(line)

    return out


def _remove_consecutive_duplicate_blocks(text: str) -> str:
    """
    處理一整段重複貼上的情況。
    """
    lines = [ln.strip() for ln in text.split("\n")]
    if not lines:
        return text

    blocks = []
    current = []

    for line in lines:
        if line:
            current.append(line)
        else:
            if current:
                blocks.append("\n".join(current))
                current = []
    if current:
        blocks.append("\n".join(current))

    out_blocks = []
    prev_norm = None

    for block in blocks:
        norm = _normalize_line_for_compare(block)
        if norm == prev_norm:
            continue
        out_blocks.append(block)
        prev_norm = norm

    return "\n\n".join(out_blocks).strip()


def _remove_obvious_outro_promo(lines: List[str]) -> List[str]:
    noise_keywords = [
        "moon river",
        "i'm crossing you",
        "in style someday",
        "晚安",
        "拜拜",
        "ok晚安",
        "ok 晚安",
        "提供給大家最好的app",
        "這個最好用的app",
        "下載我們的app",
        "0800",
        "電話撥通",
        "直接來找我",
        "免費下載",
        "麥克風",
        "詐騙",
    ]

    out = []
    for line in lines:
        lower = line.strip().lower()
        if any(k in lower for k in noise_keywords):
            continue
        out.append(line)
    return out


def _finance_asr_fixes(text: str) -> str:
    """
    金融直播常見 ASR 誤字修正。
    """
    replacements = {
        "利空大碟": "利空大跌",
        "做作的機會": "做多的機會",
        "政章整理": "震盪整理",
        "紡錘現": "紡錘線",
        "紡垂現": "紡垂線",
        "避雷真": "避雷針",
        "台之期": "台指期",
        "淨空旦": "淨空單",
        "淨多旦": "淨多單",
        "季現": "季線",
        "半年現": "半年線",
        "做頭訊號": "做頭訊號",
        "量縮收虹": "量縮收紅",
        "上引現": "上引線",
        "下引現": "下引線",
        "臺機電": "台積電",
        "台機電": "台積電",
        "華幫電": "華邦電",
        "南牙科": "南亞科",
        "國安基今": "國安基金",
        "外之": "外資",
        "法人們": "法人",
        "回測季現": "回測季線",
        "高配息旺季": "高配息旺季",
        "除權除習": "除權除息",
        "殖利率高的股票": "殖利率高的股票",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def _psychology_asr_fixes(text: str) -> str:
    replacements = {
        "阿尼馬": "阿尼瑪",
        "阿尼目斯": "阿尼姆斯",
        "個體話": "個體化",
        "頭射": "投射",
        "陰影整合": "陰影整合",
        "靈魂半侶": "靈魂伴侶",
        "高敏趕": "高敏感",
        "高敏人": "高敏人",
        "依付": "依附",
        "內在小孩": "內在小孩",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def _generic_asr_fixes(text: str) -> str:
    replacements = {
        "呃 ": "",
        "啊 ": "",
        "嗯 ": "",
        "哦 ": "",
        "欸 ": "",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def _detect_domain_hint(text: str) -> str:
    sample = (text or "")[:12000].lower()
    if any(k in sample for k in [
        "盤後講股", "盤勢", "成交量", "台股", "臺股", "大盤", "外資", "台指期",
        "淨空單", "支撐", "壓力", "回檔", "拉回", "季線", "半年線"
    ]):
        return "finance"
    if any(k in sample for k in [
        "榮格", "阿尼瑪", "阿尼姆斯", "投射", "個體化", "高敏感", "靈魂伴侶",
        "陰影", "依附", "人格", "情緒", "創傷"
    ]):
        return "psychology"
    return "general"


def looks_too_short(text: str, min_chars: int = 80, min_lines: int = 3) -> bool:
    text = _collapse_blank_lines(text)
    if len(text) < min_chars:
        return True
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return len(lines) < min_lines


def clean_transcript(text: str, force_traditional: bool = True) -> str:
    text = text or ""
    if not text.strip():
        return ""

    text = _normalize_spaces(text)
    text = _collapse_blank_lines(text)

    if force_traditional:
        text = to_traditional_chinese(text)

    domain = _detect_domain_hint(text)

    text = _generic_asr_fixes(text)
    if domain == "finance":
        text = _finance_asr_fixes(text)
    elif domain == "psychology":
        text = _psychology_asr_fixes(text)

    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if not _is_mostly_noise_line(ln)]
    lines = _remove_obvious_outro_promo(lines)
    lines = _remove_consecutive_duplicate_lines(lines, max_repeat=0)
    lines = _remove_global_near_duplicate_lines(lines)

    text = "\n".join(lines)
    text = _remove_consecutive_duplicate_blocks(text)
    text = _collapse_blank_lines(text)

    # 去掉明顯無意義的超短片段列
    cleaned_lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if len(s) <= 2 and not _contains_cjk(s):
            continue
        cleaned_lines.append(s)

    text = "\n".join(cleaned_lines)
    text = _collapse_blank_lines(text)

    if force_traditional:
        text = to_traditional_chinese(text)

    return text.strip()


def _remove_summary_generic_fluff(lines: List[str], summary_language: str) -> List[str]:
    zh_fluff = [
        "希望這些總結對你有幫助",
        "如果你需要更詳細的資訊",
        "如果你需要更多資訊",
        "如果你需要更進一步的分析",
        "請告訴我",
        "請自行研究",
        "請諮詢顧問",
        "以上是總結",
        "這篇內容主要在說",
        "從你的描述中",
        "我能提取出幾個關鍵點",
        "這段內容似乎在說",
        "保持警覺",
        "後續仍需觀察",
    ]
    en_fluff = [
        "hope this helps",
        "let me know if you need more details",
        "consult a financial advisor",
        "this appears to be",
        "it is not clear",
        "more observation is needed",
    ]

    out = []
    for line in lines:
        s = line.strip()
        lower = s.lower()
        if summary_language == "zh":
            if any(x in s for x in zh_fluff):
                continue
        else:
            if any(x in lower for x in en_fluff):
                continue
        out.append(line)
    return out


def _remove_summary_noise(lines: List[str]) -> List[str]:
    noise_keywords = [
        "moon river",
        "0800",
        "app",
        "晚安",
        "拜拜",
        "電話撥通",
        "免費下載",
        "直接來找我",
        "麥克風",
    ]
    out = []
    for line in lines:
        lower = line.strip().lower()
        if any(k in lower for k in noise_keywords):
            continue
        out.append(line)
    return out


def _fix_summary_number_dump(text: str) -> str:
    lines = text.splitlines()
    out = []

    for line in lines:
        s = line.strip()
        if not s:
            out.append(line)
            continue

        if re.fullmatch(r"[\d\.\,\，\、\-\s]+", s):
            continue

        digits = sum(ch.isdigit() for ch in s)
        cjk = sum("\u4e00" <= ch <= "\u9fff" for ch in s)
        if digits >= 8 and cjk <= 4:
            continue

        out.append(line)

    text = "\n".join(out)
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
    return _collapse_blank_lines(text)


def clean_summary(text: str, summary_language: str = "zh") -> str:
    text = text or ""
    if not text.strip():
        return ""

    text = _normalize_spaces(text)
    text = _collapse_blank_lines(text)

    if summary_language == "zh":
        text = to_traditional_chinese(text)

    lines = [ln.rstrip() for ln in text.splitlines()]
    lines = _remove_summary_noise(lines)
    lines = _remove_summary_generic_fluff(lines, summary_language)
    lines = _remove_consecutive_duplicate_lines(lines, max_repeat=0)

    text = "\n".join(lines)
    text = _fix_summary_number_dump(text)
    text = _collapse_blank_lines(text)

    # 保留標題 / 條列格式，但去掉尾端多餘空話
    text = re.sub(r"\n{3,}", "\n\n", text)

    if summary_language == "zh":
        text = to_traditional_chinese(text)

    return text.strip()
