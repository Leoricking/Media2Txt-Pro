import os
import re
from typing import List, Dict, Tuple, Optional

import requests

from pipeline.cleaner import clean_summary, to_traditional_chinese

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate").strip()
DEFAULT_OLLAMA_MODEL_ZH = os.environ.get("OLLAMA_MODEL_ZH", "qwen2.5:14b").strip()
DEFAULT_OLLAMA_MODEL_EN = os.environ.get("OLLAMA_MODEL_EN", "llama3.1").strip()
OLLAMA_TIMEOUT_SEC = int(os.environ.get("OLLAMA_TIMEOUT_SEC", "300") or "300")


# =========================
# Runtime helpers
# =========================

def _is_stopped(stop_flag) -> bool:
    return bool(stop_flag and stop_flag.get("stop"))


def _raise_if_stopped(stop_flag):
    if _is_stopped(stop_flag):
        raise RuntimeError("Summary stopped by user.")


def _resolve_model(summary_language: str) -> str:
    return DEFAULT_OLLAMA_MODEL_EN if summary_language == "en" else DEFAULT_OLLAMA_MODEL_ZH


def _collapse_blank_lines(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _contains_any(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)


def _looks_mostly_english(text: str) -> bool:
    if not text:
        return False
    ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in text)
    cjk_chars = sum("\u4e00" <= ch <= "\u9fff" for ch in text)
    return ascii_letters > max(80, cjk_chars * 2)


def _split_text(text: str, chunk_size: int = 6500, overlap: int = 350) -> List[str]:
    text = _collapse_blank_lines(text)
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        piece = text[start:end]

        if end < n:
            last_break = max(
                piece.rfind("\n\n"),
                piece.rfind("\n"),
                piece.rfind("。"),
                piece.rfind("！"),
                piece.rfind("？"),
                piece.rfind(". "),
                piece.rfind("; "),
            )
            if last_break > int(chunk_size * 0.55):
                end = start + last_break + 1
                piece = text[start:end]

        chunks.append(piece.strip())

        if end >= n:
            break

        start = max(end - overlap, start + 1)

    return [c for c in chunks if c.strip()]


def _call_ollama(prompt: str, summary_language: str, stop_flag=None, temperature: float = 0.02) -> str:
    _raise_if_stopped(stop_flag)

    model_name = _resolve_model(summary_language)
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.85,
        },
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT_SEC)
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("response") or "").strip()
        if not text:
            raise RuntimeError(f"Ollama returned empty response. model={model_name}")
        return text
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Failed to call Ollama. model={model_name}. Please make sure Ollama is running and the model is available. Detail: {e}"
        ) from e


# =========================
# Domain detection
# =========================

def detect_domain(title: str, transcript: str) -> str:
    sample = f"{title}\n{transcript[:30000]}"

    finance_live_keywords = [
        "盤後講股", "盤勢", "直播", "大盤", "台股", "臺股", "美股",
        "成交量", "震盪", "上影線", "下影線", "避雷針", "紡錘線", "紡垂線",
        "法人", "外資", "投信", "自營商", "國安基金",
        "台指期", "期貨", "選擇權", "淨空單", "淨多單",
        "支撐", "壓力", "突破", "跌破", "回檔", "拉回",
        "季線", "半年線", "翻多", "翻空", "做頭", "轉折",
        "analysis", "market recap", "market outlook", "price action", "stock market",
    ]

    finance_education_keywords = [
        "房貸", "還房貸", "ETF", "槓桿", "資產配置", "現金流", "投資報酬率", "報酬率",
        "財務自由", "複利", "本金", "貸款", "年化", "殖利率", "資金成本",
        "mortgage", "compound interest", "portfolio", "cash flow", "allocation", "annual return",
        "提早還房貸", "房貸利率", "年化報酬率", "銀行", "負債",
        "享受", "富有", "配得感", "頻率", "心流", "有錢人", "財富自由",
    ]

    psychology_growth_keywords = [
        "榮格", "投射", "阿尼瑪", "阿尼姆斯", "個體化", "靈魂伴侶", "高敏感", "高敏人",
        "人格", "創傷", "情緒", "依附", "自我成長", "陰影", "覺醒", "界線",
        "psychology", "trauma", "attachment", "projection", "inner child", "shadow", "growth",
        "反人性", "人間清醒", "底層邏輯", "聰明人", "認知", "內在成長", "情緒成熟",
    ]

    science_keywords = [
        "研究", "實驗", "模型", "數據", "結果", "假說", "論文",
        "benchmark", "study", "experiment", "evidence", "hypothesis", "dataset",
    ]
    medical_keywords = [
        "症狀", "診斷", "治療", "藥物", "病人", "臨床", "副作用",
        "醫學", "健康", "symptom", "diagnosis", "treatment", "clinical", "trial",
    ]
    legal_keywords = [
        "法律", "法規", "判決", "合約", "責任", "權利", "義務",
        "law", "legal", "contract", "liability", "compliance",
    ]
    technology_course_keywords = [
        "韋東山", "嵌入式", "裸機", "驅動大全", "驅動", "核心", "內核",
        "linux驅動", "linux 3.4.2", "u-boot", "uboot", "busybox", "根文件系統",
        "makefile", "交叉編譯", "toolchain", "arm", "gpio", "i2c", "iic", "spi",
        "lcd", "framebuffer", "顯存", "freetype", "字體", "數位相框", "文件瀏覽器",
        "nor flash", "nand flash", "mtd", "input subsystem", "輸入子系統",
        "系統調用", "segmentation fault", "段錯誤", "gdb", "strace", "mmap",
        "kernel", "driver", "device tree", "dts", "module", "insmod", "rmmod",
    ]

    technology_keywords = [
        "程式", "系統", "架構", "部署", "除錯", "效能", "延遲",
        "throughput", "latency", "api", "backend", "frontend",
        "database", "cloud", "gpu", "cuda", "kernel", "bug",
    ]
    business_keywords = [
        "商業模式", "營收", "成本", "毛利", "市場", "策略", "品牌",
        "客戶", "ROI", "TCO", "business", "revenue", "cost", "strategy",
    ]
    education_keywords = [
        "教學", "課程", "學習", "重點整理", "筆記", "老師", "學生",
        "lesson", "course", "teaching", "learning",
    ]

    if _contains_any(sample, finance_live_keywords):
        return "finance_live"
    if _contains_any(sample, finance_education_keywords):
        return "finance_education"
    if _contains_any(sample, psychology_growth_keywords):
        return "psychology_growth"
    if _contains_any(sample, medical_keywords):
        return "medicine"
    if _contains_any(sample, science_keywords):
        return "science"
    if _contains_any(sample, legal_keywords):
        return "legal"
    if _contains_any(sample, technology_course_keywords):
        return "technology_course"
    if _contains_any(sample, technology_keywords):
        return "technology"
    if _contains_any(sample, business_keywords):
        return "business"
    if _contains_any(sample, education_keywords):
        return "education"
    return "general"


# =========================
# Language / style rules
# =========================

def _language_instruction(summary_language: str) -> str:
    if summary_language == "en":
        return (
            "Write the summary in clear, professional English only. "
            "Do not output Chinese. "
            "Do not mix languages."
        )
    return (
        "請只用繁體中文輸出。"
        "禁止輸出英文摘要。"
        "禁止中英混寫。"
        "若原文是簡體中文，請轉成繁體中文後再輸出。"
    )


def _domain_instruction(domain: str, summary_language: str) -> str:
    zh = summary_language != "en"

    if domain == "finance_live":
        return (
            "你是專業的台股盤後直播 / 解盤摘要助手。\n"
            "你要輸出可拿來操作與風險判斷的摘要。\n"
            "你必須像交易筆記整理員，不是心得文寫手。\n"
            "核心規則：\n"
            "1. 一定抽極端數據與意義\n"
            "2. 一定抽 K線 / 技術面判讀\n"
            "3. 一定抽條件分支\n"
            "4. 一定抽關鍵價位 / 區間\n"
            "5. 一定分開可做 / 避開\n"
            "6. 一定抽操作結論\n"
            "7. 絕對不能自補不存在的股票、數字或價位\n"
            "8. 不得保留 App、歌詞、0800、晚安拜拜"
        ) if zh else (
            "You are an expert Taiwan market livestream summarizer.\n"
            "Your summary must read like an actionable trading note.\n"
            "Core rules:\n"
            "1. extract extreme figures and their meaning\n"
            "2. extract candlestick / technical interpretation\n"
            "3. extract conditional branches\n"
            "4. extract key levels and price ranges\n"
            "5. separate what to do vs what to avoid\n"
            "6. extract the trading conclusion\n"
            "7. never invent stocks, numbers, or levels\n"
            "8. exclude app promotion, lyrics, hotline numbers, and outro chatter"
        )

    if domain == "finance_education":
        return (
            "你是金融教育 / 理財內容摘要助手。\n"
            "核心規則：\n"
            "1. 一定分開『主張』\n"
            "2. 一定分開『假設條件』\n"
            "3. 一定整理『計算邏輯』\n"
            "4. 一定整理『練習 / 實作建議』\n"
            "5. 一定整理『限制 / 風險』\n"
            "6. 不可把講者推論包裝成客觀事實\n"
            "7. 若有利率、報酬率、房價、貸款、本金、複利模型，必須保留"
        ) if zh else (
            "You are a finance education summarizer.\n"
            "Core rules:\n"
            "1. separate the main claim\n"
            "2. separate assumptions\n"
            "3. organize the calculation logic\n"
            "4. extract practical exercises / actions\n"
            "5. extract limitations / risks\n"
            "6. do not present the speaker's reasoning as objective fact\n"
            "7. preserve rates, returns, housing prices, loan size, principal, and compounding logic"
        )

    if domain == "psychology_growth":
        return (
            "你是心理學 / 哲學 / 自我成長內容摘要助手。\n"
            "核心規則：\n"
            "1. 一定輸出論點樹\n"
            "2. 一定保留專有名詞與理論骨架\n"
            "3. 一定保留影片中的關鍵比喻或推導\n"
            "4. 一定列出可執行建議\n"
            "5. 一定指出可能誇飾 / 延伸之處\n"
            "6. 不可只寫情緒性總結\n"
            "7. 不可寫成雞湯文"
        ) if zh else (
            "You are a psychology / philosophy / self-growth summarizer.\n"
            "Core rules:\n"
            "1. produce an argument tree\n"
            "2. preserve key terms and theoretical structure\n"
            "3. preserve important metaphors and reasoning steps\n"
            "4. list practical advice\n"
            "5. point out possible overreach / extension\n"
            "6. do not reduce it to emotional commentary\n"
            "7. do not write inspirational fluff"
        )

    if domain == "technology_course":
        return (
            "你是嵌入式 Linux / 驅動 / 系統程式技術課程摘要助手。\n"
            "核心規則：\n"
            "1. 一定整理本課主題與學習目標\n"
            "2. 一定保留核心概念、架構、流程\n"
            "3. 一定保留關鍵 API / 指令 / 檔案 / Makefile / kernel 設定\n"
            "4. 一定整理除錯方法與錯誤現象\n"
            "5. 一定列出實作步驟與可複習清單\n"
            "6. 不可寫成空泛心得，不可刪掉技術細節\n"
            "7. 若逐字稿因 ASR 造成名詞不準，請以保守方式整理，不要捏造不存在的 API"
        ) if zh else (
            "You are an embedded Linux / driver / systems programming course summarizer.\n"
            "Core rules:\n"
            "1. identify the topic and learning objective\n"
            "2. preserve core concepts, architecture, and workflow\n"
            "3. preserve APIs, commands, files, Makefile and kernel settings\n"
            "4. extract debugging methods and failure symptoms\n"
            "5. list implementation steps and a review checklist\n"
            "6. do not write vague commentary; keep technical details\n"
            "7. do not invent APIs when ASR terms are uncertain"
        )

    if domain == "general":
        return (
            "你是專業摘要助手。\n"
            "若原文有明確的 3 / 5 / 6 點結構，摘要必須對齊原結構。\n"
            "不可任意合併成泛論段落。"
        ) if zh else (
            "You are a professional summarizer.\n"
            "If the source has an explicit 3 / 5 / 6 point structure, preserve that structure.\n"
            "Do not merge it into vague generic commentary."
        )

    mapping_zh = {
        "science": "你是科學與研究摘要助手。請清楚說明研究問題、方法、主要發現、限制與實際意義。",
        "medicine": "你是醫學摘要助手。請清楚整理症狀、診斷、治療、風險、限制與適用條件，不得誇大療效。",
        "technology": "你是技術摘要助手。請說明問題、原因、架構、解法、效能影響、風險與取捨。",
        "business": "你是商業摘要助手。請整理商業邏輯、目標客群、成本、營收、競爭優勢、風險與策略意義。",
        "legal": "你是法律摘要助手。請區分明確規則、條件、責任、例外與風險，不可混淆推測與事實。",
        "education": "你是教學內容摘要助手。請整理主題、學習重點、概念之間的關係、常見錯誤與可執行練習方向。",
    }
    mapping_en = {
        "science": "You are a science and research summarizer. Clearly state the question, method, findings, limitations, and implications.",
        "medicine": "You are a medical summarizer. Clearly organize symptoms, diagnosis, treatment, risks, limitations, and applicability.",
        "technology": "You are a technical summarizer. Explain the problem, root cause, architecture, solution, performance impact, risks, and tradeoffs.",
        "business": "You are a business summarizer. Explain business logic, target users, costs, revenue, moat, risks, and strategic meaning.",
        "legal": "You are a legal summarizer. Distinguish explicit rules, conditions, obligations, exceptions, and risks.",
        "education": "You are an educational summarizer. Organize the topic, key concepts, concept links, common mistakes, and practical study directions.",
    }

    return mapping_en.get(domain, "You are a professional summarizer.") if summary_language == "en" else mapping_zh.get(domain, "你是專業摘要助手。")


def _format_instruction(summary_language: str, domain: str) -> str:
    if summary_language == "en":
        if domain == "finance_live":
            return (
                "Use this exact structure:\n"
                "1. Core takeaway\n"
                "2. Extreme figures and why they matter\n"
                "3. Technical / candlestick interpretation\n"
                "4. Conditional scenarios and key levels\n"
                "5. What to do / what to avoid\n"
                "6. Trading conclusion"
            )
        if domain == "finance_education":
            return (
                "Use this exact structure:\n"
                "1. Core takeaway\n"
                "2. Main claim\n"
                "3. Assumptions and calculation logic\n"
                "4. Practice / action ideas\n"
                "5. Limitations and risks"
            )
        if domain == "psychology_growth":
            return (
                "Use this exact structure:\n"
                "1. Core claim\n"
                "2. Main framework / theory\n"
                "3. Examples / metaphors used\n"
                "4. Practical advice\n"
                "5. Possible overreach / caution"
            )
        if domain == "technology_course":
            return (
                "Use this exact structure:\n"
                "1. Lesson topic\n"
                "2. Core concepts\n"
                "3. Implementation / operation flow\n"
                "4. Key APIs / commands / files\n"
                "5. Program architecture\n"
                "6. Debugging focus\n"
                "7. Common mistakes\n"
                "8. Review checklist"
            )
        return (
            "Use this exact structure:\n"
            "1. Core takeaway\n"
            "2. Structured points aligned to source structure\n"
            "3. Key details / figures / conditions\n"
            "4. Actionable conclusion"
        )

    if domain == "finance_live":
        return (
            "輸出格式固定為：\n"
            "1. 核心結論\n"
            "2. 極端數據與其意義\n"
            "3. 技術面 / K線判讀\n"
            "4. 關鍵條件句與價位\n"
            "5. 可做與避開\n"
            "6. 操作結論"
        )
    if domain == "finance_education":
        return (
            "輸出格式固定為：\n"
            "1. 核心結論\n"
            "2. 影片主張\n"
            "3. 假設條件與計算邏輯\n"
            "4. 練習 / 實作建議\n"
            "5. 限制與風險"
        )
    if domain == "psychology_growth":
        return (
            "輸出格式固定為：\n"
            "1. 核心主張\n"
            "2. 主要理論框架\n"
            "3. 影片使用的例子 / 比喻\n"
            "4. 可執行建議\n"
            "5. 可能誇飾 / 延伸之處"
        )
    if domain == "technology_course":
        return (
            "輸出格式固定為：\n"
            "1. 本課主題\n"
            "2. 核心概念\n"
            "3. 操作 / 實作流程\n"
            "4. 關鍵 API / 指令 / 檔案\n"
            "5. 程式架構\n"
            "6. 除錯重點\n"
            "7. 易錯點\n"
            "8. 複習清單"
        )
    return (
        "輸出格式固定為：\n"
        "1. 核心結論\n"
        "2. 依原文結構對齊的重點條列\n"
        "3. 關鍵細節 / 數字 / 條件\n"
        "4. 可執行結論"
    )


# =========================
# Structure / focus extraction
# =========================

def _extract_focus_lines(domain: str, text: str) -> str:
    lines = [ln.strip() for ln in _collapse_blank_lines(text).splitlines()]
    kept = []

    if domain == "finance_live":
        keywords = [
            "成交量", "兆", "震盪", "上引線", "下引線", "避雷針", "紡垂線", "紡錘線",
            "外資", "法人", "淨空單", "台指期", "拉回", "回檔", "做多", "翻多", "買", "賣",
            "支撐", "壓力", "季線", "半年線", "談判破裂", "戰爭", "量縮收紅", "做頭",
            "台積電", "鴻海", "廣達", "國巨", "南亞科", "華邦電", "旺宏", "力積電",
            "38921", "37164", "35579", "3342", "4050", "1757", "1.4兆", "4.4萬口",
            "2050", "2060", "2030", "2125", "2135", "2330",
        ]
    elif domain == "finance_education":
        keywords = [
            "房貸", "貸款", "利率", "年化", "複利", "報酬率", "現金流", "房價", "本金",
            "假設", "投資", "ETF", "30年", "20年", "報酬", "資金成本",
            "500萬", "1500萬", "2000萬", "2.1%", "7%", "3800萬", "財務自由",
            "配得感", "頻率", "心流", "每日三件", "21天", "享受", "三件事", "五個",
        ]
    elif domain == "psychology_growth":
        keywords = [
            "榮格", "投射", "阿尼瑪", "阿尼姆斯", "個體化", "靈魂伴侶", "高敏感",
            "界線", "陰影", "創傷", "依附", "情緒", "人格", "覺醒", "15%到20%", "5到10倍",
            "內在小孩", "高敏人", "人間清醒", "反人性", "底層邏輯", "情緒解離", "灰度思維",
            "六個", "五個", "三個", "三件事",
        ]
    elif domain == "technology_course":
        keywords = [
            "Linux", "嵌入式", "驅動", "核心", "內核", "Makefile", "API", "函數", "系統調用",
            "kernel", "driver", "module", "insmod", "rmmod", "GPIO", "I2C", "IIC", "SPI",
            "LCD", "framebuffer", "顯存", "freetype", "mmap", "gdb", "strace", "段錯誤",
            "流程", "步驟", "編譯", "配置", "測試", "除錯", "錯誤", "文件", "程式", "代碼",
            "NorFlash", "NandFlash", "U-Boot", "根文件系統", "輸入子系統", "數位相框",
        ]
    else:
        keywords = ["第1", "第一", "第二", "第三", "第四", "第五", "第六", "三個", "五個", "六個", "3個", "5個", "6個"]

    noise = [
        "moon river", "晚安", "拜拜", "app", "0800", "電話撥通",
        "麥克風", "免費下載", "直接來找我", "提供給大家最好的app",
    ]

    for line in lines:
        lower = line.lower()
        if any(n in lower for n in noise):
            continue
        if any(k.lower() in lower for k in keywords):
            kept.append(line)

    kept = kept[:360]
    return _collapse_blank_lines("\n".join(kept))


def _extract_enumeration_target(text: str, domain: str) -> Optional[int]:
    """
    若原文是明確 3 / 5 / 6 點，嘗試抓出來，讓 summary 對齊。
    """
    sample = _collapse_blank_lines(text)[:12000]

    patterns = [
        r"(\d+)\s*個(?:特質|真相|重點|關鍵|方法|原則|步驟|原因)",
        r"(\d+)\s*件事",
        r"第[一二三四五六七八九十1-9]",
        r"(三|五|六)\s*個",
    ]

    if domain in ("finance_live",):
        return None

    # 先抓阿拉伯數字
    m = re.search(r"([356])\s*(?:個|件事)", sample)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass

    # 抓中文數字
    if re.search(r"三\s*(?:個|件事)", sample):
        return 3
    if re.search(r"五\s*個", sample):
        return 5
    if re.search(r"六\s*個", sample):
        return 6

    # 若出現大量「第一、第二...」
    count = 0
    for token in ["第一", "第二", "第三", "第四", "第五", "第六"]:
        if token in sample:
            count += 1
    if count in (3, 5, 6):
        return count

    return None


def _extract_numeric_mapping(domain: str, text: str) -> str:
    """
    數字密集文：先做 數字 → 意義 → 條件 的候選映射。
    """
    lines = [ln.strip() for ln in _collapse_blank_lines(text).splitlines()]
    out = []

    num_pattern = re.compile(r"(\d[\d\.,]*\s*(?:兆|萬口|點|元|%|年|月|日|倍)?)")

    for line in lines:
        nums = num_pattern.findall(line)
        if not nums:
            continue

        lower = line.lower()

        if domain == "finance_live":
            if any(k in lower for k in ["成交量", "震盪", "上引線", "下引線", "外資", "淨空單", "台指期", "高點", "低點", "支撐", "壓力", "季線", "半年線", "跌破", "站上", "回檔", "拉回"]):
                out.append(line)
        elif domain == "finance_education":
            if any(k in lower for k in ["利率", "房貸", "貸款", "房價", "年化", "報酬率", "本金", "現金流", "複利", "30年", "20年", "500萬", "1500萬", "2000萬"]):
                out.append(line)
        else:
            out.append(line)

    return _collapse_blank_lines("\n".join(out[:200]))


# =========================
# Transcript normalization
# =========================

def _normalize_transcript(transcript: str, domain: str, summary_language: str) -> str:
    text = _collapse_blank_lines(transcript)

    if summary_language == "zh":
        text = to_traditional_chinese(text)

    lines = [ln.strip() for ln in text.splitlines()]
    out = []
    prev_norm = None
    repeat_count = 0

    noise_keywords = [
        "moon river", "晚安", "拜拜", "app", "0800", "電話撥通",
        "麥克風", "免費下載", "直接來找我", "下載我們的app",
    ]

    for line in lines:
        if not line:
            continue

        lower = line.lower()
        if any(k in lower for k in noise_keywords):
            continue

        norm = re.sub(r"\s+", "", line)
        if prev_norm == norm:
            repeat_count += 1
            if repeat_count >= 1:
                continue
        else:
            repeat_count = 0
            prev_norm = norm

        out.append(line)

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if domain == "finance_live":
        replacements = {
            "利空大碟": "利空大跌",
            "做作的機會": "做多的機會",
            "政章整理": "震盪整理",
            "量縮收虹": "量縮收紅",
            "上引現": "上引線",
            "下引現": "下引線",
            "淨空旦": "淨空單",
            "台之期": "台指期",
            "季現": "季線",
            "半年現": "半年線",
            "紡錘現": "紡錘線",
            "紡垂現": "紡垂線",
        }
        for a, b in replacements.items():
            text = text.replace(a, b)

    if domain == "psychology_growth":
        replacements = {
            "阿尼馬": "阿尼瑪",
            "阿尼目斯": "阿尼姆斯",
            "個體話": "個體化",
            "頭射": "投射",
            "高敏趕": "高敏感",
            "依付": "依附",
            "陰影整和": "陰影整合",
        }
        for a, b in replacements.items():
            text = text.replace(a, b)

    return text.strip()


# =========================
# Prompt builders
# =========================

def _build_chunk_prompt(
    domain: str,
    title: str,
    chunk_text: str,
    transcript_source: str,
    media_source: str,
    summary_language: str,
    chunk_index: int,
    total_chunks: int,
    enum_target: Optional[int],
) -> str:
    focus_lines = _extract_focus_lines(domain, chunk_text)
    numeric_map = _extract_numeric_mapping(domain, chunk_text)

    extra = ""
    if domain == "finance_live":
        extra = (
            "金融直播額外規則：\n"
            "- 每個數字都要綁定意義\n"
            "- 一定分開「可做」與「避開」\n"
            "- 若有條件句，必須完整保留成條件式\n"
            "- 若有買賣區間，必須保留完整區間與理由\n"
            "- 必須保留極端數據與技術判讀\n"
            "- 不可自補不存在的股票與價位\n"
        )
    elif domain == "finance_education":
        extra = (
            "金融教育額外規則：\n"
            "- 一定區分『主張』與『假設條件』\n"
            "- 若有數字模型，必須保留計算邏輯\n"
            "- 若影片有練習方式或實作建議，必須保留\n"
            "- 必須寫出限制 / 風險\n"
        )
    elif domain == "psychology_growth":
        extra = (
            "心理 / 成長額外規則：\n"
            "- 一定寫成論點樹\n"
            "- 要保留理論名詞與比喻\n"
            "- 若有具體建議，必須列出\n"
            "- 若內容有誇飾性講法，要標出可能延伸之處\n"
        )
    elif domain == "technology_course":
        extra = (
            "技術課程額外規則：\n"
            "- 本段若包含程式碼、API、檔名、命令、Makefile 規則，必須保留\n"
            "- 要分清楚：概念、操作、程式架構、除錯方法\n"
            "- 若講到錯誤現象、測試方法、核心設定，要明確列出\n"
            "- 不要把技術名詞改成泛泛而談\n"
        )
    else:
        if enum_target:
            extra = f"原文明顯是 {enum_target} 點結構，請盡量保持相同結構，不可任意合併。"

    return f"""
You are a cross-domain elite summarization assistant.
Current domain: {domain}

{_language_instruction(summary_language)}
{_domain_instruction(domain, summary_language)}

Task:
Create a chunk-level expert summary for chunk {chunk_index}/{total_chunks}.
This is not the final summary.
Do not write intro or filler.

Title:
{title}

Media source: {media_source}
Transcript source: {transcript_source}

Ignore:
- repeated filler
- outro chatter
- app promotion
- singing
- irrelevant self-promotion
- hotline numbers
- repetitive rhetorical questions

{extra}

高價值候選句：
--------------------
{focus_lines}
--------------------

數字 → 意義 → 條件 候選映射：
--------------------
{numeric_map}
--------------------

{_format_instruction(summary_language, domain)}

Transcript chunk:
--------------------
{chunk_text}
--------------------
""".strip()


def _build_final_prompt(
    domain: str,
    title: str,
    merged_chunk_notes: str,
    transcript_source: str,
    media_source: str,
    summary_language: str,
    transcript: str,
    enum_target: Optional[int],
) -> str:
    focus_lines = _extract_focus_lines(domain, transcript)
    numeric_map = _extract_numeric_mapping(domain, transcript)

    extra = ""
    if domain == "finance_live":
        extra = (
            "最終金融直播規則：\n"
            "- 一定保留極端數據與其意義\n"
            "- 一定保留 K 線 / 技術面判讀\n"
            "- 一定保留條件句與價位\n"
            "- 一定分開可做與避開\n"
            "- 一定保留講者最終操作結論\n"
            "- 不得輸出空泛投資勸世文\n"
            "- 價位若有多組，全部要保留，不可只寫一組\n"
            "- 絕對不能自補不存在的股票、數字、價位\n"
        )
    elif domain == "finance_education":
        extra = (
            "最終金融教育規則：\n"
            "- 一定分開『主張』『假設』『計算邏輯』『練習 / 實作』『限制與風險』\n"
            "- 一定保留具體數字與計算邏輯\n"
            "- 一定寫出哪些前提成立時，影片主張才比較可能成立\n"
            "- 不可把影片中的推論包裝成絕對事實\n"
        )
    elif domain == "psychology_growth":
        extra = (
            "最終心理 / 成長規則：\n"
            "- 一定輸出論點樹\n"
            "- 不可寫成雞湯勵志文\n"
            "- 要指出可能誇飾 / 延伸之處\n"
            "- 要保留可執行建議\n"
            "- 要保留理論骨架，不要只剩漂亮話\n"
        )
    elif domain == "technology_course":
        extra = (
            "最終技術課程規則：\n"
            "- 一定輸出『本課主題 / 核心概念 / 實作流程 / 關鍵 API 指令檔案 / 程式架構 / 除錯重點 / 易錯點 / 複習清單』\n"
            "- 必須保留 embedded Linux、kernel、driver、Makefile、API、命令、檔案路徑等技術細節\n"
            "- 若逐字稿名詞不確定，只能保守整理，不可捏造不存在的函數或參數\n"
            "- 不可寫成心得文或泛用學習建議\n"
        )
    else:
        if enum_target:
            extra = f"原文明顯是 {enum_target} 點結構，最終摘要必須盡量保持 {enum_target} 點，不可任意合併成泛論段落。"

    return f"""
You are a cross-domain elite summarization assistant.
Current domain: {domain}

{_language_instruction(summary_language)}
{_domain_instruction(domain, summary_language)}

Task:
Merge the notes below into one final high-quality expert summary.

Rules:
- No generic filler
- No made-up facts
- Keep key numbers, conditions, risks, and logic
- Remove noise
- Preserve thresholds, named entities, time points, and explicit actions if present
- Do not dump broken numbers
- Keep structure strict and useful

{extra}

Title:
{title}

Media source: {media_source}
Transcript source: {transcript_source}

高價值候選句：
--------------------
{focus_lines}
--------------------

數字 → 意義 → 條件 候選映射：
--------------------
{numeric_map}
--------------------

{_format_instruction(summary_language, domain)}

Chunk notes:
--------------------
{merged_chunk_notes}
--------------------
""".strip()


def _build_rewrite_prompt(summary_text: str, summary_language: str) -> str:
    if summary_language == "en":
        return f"""
Rewrite the following summary into clean professional English only.
Do not output Chinese.
Do not add new facts.
Keep the original structure and meaning.

Summary:
--------------------
{summary_text}
--------------------
""".strip()

    return f"""
請把下面這份摘要改寫成自然、專業、只用繁體中文的版本。
禁止輸出英文。
禁止中英混寫。
不要新增原文沒有的事實。
保留原本結構與意思。
刪除過度禮貌、空泛、無資訊價值的收尾。

摘要：
--------------------
{summary_text}
--------------------
""".strip()


# =========================
# Post-processing
# =========================

def _remove_obvious_promo_noise(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    cleaned = []

    promo_keywords = [
        "app", "下載我們的app", "0800", "直接來找我", "電話撥通",
        "moon river", "晚安", "拜拜", "麥克風", "免費下載",
    ]

    for line in lines:
        lower = line.lower()
        if any(k in lower for k in promo_keywords):
            continue
        cleaned.append(line)

    return _collapse_blank_lines("\n".join(cleaned))


def _fix_broken_number_dump(text: str, domain: str, summary_language: str) -> str:
    if domain not in ("finance_live", "finance_education"):
        return text

    lines = text.splitlines()
    fixed = []
    number_dump_pattern = re.compile(r"^[\-\•\d\.\s、,，]+$")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            fixed.append(line)
            continue

        if number_dump_pattern.match(stripped):
            continue

        digits = sum(ch.isdigit() for ch in stripped)
        cjk = sum("\u4e00" <= ch <= "\u9fff" for ch in stripped)
        letters = sum(ch.isalpha() for ch in stripped)

        if digits >= 8 and cjk <= 6 and letters <= 8:
            continue

        fixed.append(line)

    text = _collapse_blank_lines("\n".join(fixed))
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    if summary_language == "zh":
        text = to_traditional_chinese(text)

    return text


def _harden_summary(text: str, domain: str, summary_language: str) -> str:
    lines = text.splitlines()
    cleaned = []

    generic_zh = [
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

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if not stripped:
            cleaned.append(line)
            continue

        if any(g in stripped for g in generic_zh):
            continue
        if any(g in lower for g in en_fluff):
            continue

        cleaned.append(line)

    text = _collapse_blank_lines("\n".join(cleaned))

    if summary_language == "zh":
        text = to_traditional_chinese(text)

    return text.strip()


def _enforce_summary_language(summary_text: str, summary_language: str, stop_flag=None) -> str:
    summary_text = (summary_text or "").strip()

    if summary_language == "zh":
        if _looks_mostly_english(summary_text):
            rewritten = _call_ollama(_build_rewrite_prompt(summary_text, "zh"), "zh", stop_flag=stop_flag)
            return clean_summary(rewritten, summary_language="zh")
        return clean_summary(summary_text, summary_language="zh")

    if summary_language == "en":
        if not _looks_mostly_english(summary_text):
            rewritten = _call_ollama(_build_rewrite_prompt(summary_text, "en"), "en", stop_flag=stop_flag)
            return clean_summary(rewritten, summary_language="en")
        return clean_summary(summary_text, summary_language="en")

    return clean_summary(summary_text, summary_language=summary_language)


def _post_process_summary(summary_text: str, domain: str, summary_language: str) -> str:
    text = summary_text or ""
    text = _remove_obvious_promo_noise(text)
    text = _fix_broken_number_dump(text, domain, summary_language)
    text = clean_summary(text, summary_language=summary_language)
    text = _harden_summary(text, domain, summary_language)

    if summary_language == "zh":
        text = to_traditional_chinese(text)

    return text.strip()



# =========================
# Timeout-safe fallback summary
# =========================

def _select_fallback_lines(domain: str, transcript: str, max_lines: int = 80) -> List[str]:
    text = _collapse_blank_lines(transcript)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    noise = [
        "moon river", "晚安", "拜拜", "app", "0800", "電話撥通",
        "免費下載", "訂閱", "按讚", "分享", "小鈴鐺",
    ]

    preferred_keywords = []
    if domain == "technology_course":
        preferred_keywords = [
            "linux", "驅動", "核心", "內核", "kernel", "driver", "makefile",
            "api", "函數", "系統調用", "gdb", "strace", "段錯誤", "mmap",
            "gpio", "i2c", "iic", "spi", "lcd", "framebuffer", "freetype",
            "編譯", "配置", "測試", "除錯", "錯誤", "流程", "步驟", "程式", "代碼",
        ]
    elif domain == "technology":
        preferred_keywords = ["架構", "程式", "api", "系統", "除錯", "效能", "bug", "部署", "kernel", "driver"]
    elif domain.startswith("finance"):
        preferred_keywords = ["利率", "報酬", "價格", "成交量", "支撐", "壓力", "風險", "條件", "假設"]
    elif domain == "psychology_growth":
        preferred_keywords = ["理論", "情緒", "投射", "界線", "創傷", "建議", "關係", "自我"]

    selected = []
    seen = set()

    def add_line(line: str):
        norm = re.sub(r"\s+", "", line.lower())
        if not norm or norm in seen:
            return
        if any(n in norm for n in noise):
            return
        if len(line) < 8:
            return
        seen.add(norm)
        selected.append(line)

    for line in lines:
        lower = line.lower()
        if preferred_keywords and any(k.lower() in lower for k in preferred_keywords):
            add_line(line)
            if len(selected) >= max_lines:
                return selected

    # 補頭中尾，避免只摘到單一區段。
    if lines:
        picks = []
        picks.extend(lines[:20])
        mid = len(lines) // 2
        picks.extend(lines[max(0, mid - 10): mid + 10])
        picks.extend(lines[-20:])
        for line in picks:
            add_line(line)
            if len(selected) >= max_lines:
                break

    return selected[:max_lines]


def build_fallback_summary(
    title: str,
    transcript: str,
    summary_error: str = "",
    summary_language: str = "zh",
    transcript_source: str = "",
    media_source: str = "",
) -> str:
    """
    Ollama timeout / error 時的保底摘要。
    這個函式不呼叫任何 LLM，只根據已成功產出的 transcript 產生可保存內容，
    避免 Whisper 已完成但整支影片沒有輸出。
    """
    title = (title or "").strip()
    transcript = _collapse_blank_lines(transcript)

    if summary_language == "zh":
        title = to_traditional_chinese(title)
        transcript = to_traditional_chinese(transcript)

    domain = detect_domain(title, transcript)
    lines = _select_fallback_lines(domain, transcript, max_lines=70)

    if summary_language == "en":
        if domain == "technology_course":
            header = [
                "[Fallback summary]",
                "The transcript was completed, but Ollama summary generation timed out or failed.",
                "The following is an extractive technical fallback summary generated from the transcript.",
                "",
                "1. Lesson topic",
                f"- {title or 'Untitled'}",
                "",
                "2. Key transcript excerpts / technical points",
            ]
        else:
            header = [
                "[Fallback summary]",
                "The transcript was completed, but Ollama summary generation timed out or failed.",
                "The following extractive summary was generated from the transcript.",
                "",
                "1. Core topic",
                f"- {title or 'Untitled'}",
                "",
                "2. Key transcript excerpts",
            ]
        body = [f"- {ln}" for ln in lines] or ["- No reliable transcript lines were available for fallback extraction."]
        tail = [
            "",
            "3. Status",
            f"- Transcript source: {transcript_source}",
            f"- Media source: {media_source}",
            f"- Summary status: fallback_error",
        ]
        if summary_error:
            tail.append(f"- Error: {summary_error}")
        return _collapse_blank_lines("\n".join(header + body + tail))

    if domain == "technology_course":
        header = [
            "【保底摘要】",
            "本影片已完成 Whisper 轉錄，但 Ollama 摘要逾時或失敗。",
            "以下是不呼叫 LLM、直接根據逐字稿抽取的技術保底摘要，避免轉錄成果遺失。",
            "",
            "1. 本課主題",
            f"- {title or '未命名'}",
            "",
            "2. 核心概念 / 操作流程 / 關鍵技術片段",
        ]
    else:
        header = [
            "【保底摘要】",
            "本影片已完成 Whisper 轉錄，但 Ollama 摘要逾時或失敗。",
            "以下是不呼叫 LLM、直接根據逐字稿抽取的保底摘要。",
            "",
            "1. 主題",
            f"- {title or '未命名'}",
            "",
            "2. 逐字稿關鍵片段",
        ]

    body = [f"- {ln}" for ln in lines] or ["- 沒有足夠可靠的逐字稿片段可供抽取。"]
    tail = [
        "",
        "3. 狀態",
        f"- 轉錄來源：{transcript_source}",
        f"- 媒體來源：{media_source}",
        "- 摘要狀態：fallback_error",
    ]
    if summary_error:
        tail.append(f"- 錯誤原因：{summary_error}")

    return _collapse_blank_lines("\n".join(header + body + tail))

# =========================
# Public API
# =========================

def summarize(
    title: str,
    transcript: str,
    transcript_source: str,
    media_source: str,
    summary_language: str = "zh",
    stop_flag=None,
) -> str:
    _raise_if_stopped(stop_flag)

    title = (title or "").strip()
    transcript = _collapse_blank_lines(transcript)

    if summary_language == "zh":
        title = to_traditional_chinese(title)
        transcript = to_traditional_chinese(transcript)

    if not transcript:
        return "無可摘要內容。" if summary_language == "zh" else "No content available to summarize."

    domain = detect_domain(title, transcript)
    transcript = _normalize_transcript(transcript, domain, summary_language)
    enum_target = _extract_enumeration_target(transcript, domain)

    single_pass_limit = 3600 if domain == "technology_course" else 6500

    if len(transcript) <= single_pass_limit:
        prompt = _build_final_prompt(
            domain=domain,
            title=title,
            merged_chunk_notes=transcript,
            transcript_source=transcript_source,
            media_source=media_source,
            summary_language=summary_language,
            transcript=transcript,
            enum_target=enum_target,
        )
        result = _call_ollama(prompt, summary_language, stop_flag=stop_flag)
        result = _enforce_summary_language(result, summary_language, stop_flag=stop_flag)
        return _post_process_summary(result, domain, summary_language)

    chunk_size = 3200 if domain == "technology_course" else 5000
    chunks = _split_text(transcript, chunk_size=chunk_size, overlap=250)
    chunk_notes = []

    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        _raise_if_stopped(stop_flag)
        prompt = _build_chunk_prompt(
            domain=domain,
            title=title,
            chunk_text=chunk,
            transcript_source=transcript_source,
            media_source=media_source,
            summary_language=summary_language,
            chunk_index=idx,
            total_chunks=total,
            enum_target=enum_target,
        )
        note = _call_ollama(prompt, summary_language, stop_flag=stop_flag)
        note = _enforce_summary_language(note, summary_language, stop_flag=stop_flag)
        note = _post_process_summary(note, domain, summary_language)
        chunk_notes.append(f"[Chunk {idx}/{total}]\n{note}")

    merged = "\n\n".join(chunk_notes)

    final_prompt = _build_final_prompt(
        domain=domain,
        title=title,
        merged_chunk_notes=merged,
        transcript_source=transcript_source,
        media_source=media_source,
        summary_language=summary_language,
        transcript=transcript,
        enum_target=enum_target,
    )
    result = _call_ollama(final_prompt, summary_language, stop_flag=stop_flag)
    result = _enforce_summary_language(result, summary_language, stop_flag=stop_flag)
    return _post_process_summary(result, domain, summary_language)
