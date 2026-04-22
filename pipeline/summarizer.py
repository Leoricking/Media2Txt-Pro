import os
import shutil
import subprocess
import re

from pipeline.cleaner import clean_summary, clean_transcript


def detect_content_type(title: str, transcript: str) -> str:
    text = f"{title}\n{transcript}".lower()

    finance_keywords = [
        "台股", "台北股市", "加權", "做多", "五日均線", "高點", "低點", "回檔",
        "股票", "台積電", "聯發科", "營收", "配息", "融資", "族群", "均線",
        "k線", "技術面", "翻多", "修正", "支撐", "壓力", "stock", "market",
        "earnings", "revenue", "dividend", "support", "resistance", "trend",
    ]

    lyric_keywords = [
        "lyric", "lyrics", "music video", "official audio", "chorus", "verse",
        "歌詞", "歌曲", "音樂", "副歌", "主歌",
    ]

    tutorial_keywords = [
        "教學", "步驟", "如何", "怎麼", "說明", "流程", "設定",
        "tutorial", "how to", "steps", "guide", "instruction",
    ]

    finance_score = sum(1 for kw in finance_keywords if kw in text)
    lyric_score = sum(1 for kw in lyric_keywords if kw in text)
    tutorial_score = sum(1 for kw in tutorial_keywords if kw in text)

    if finance_score >= 3:
        return "finance"
    if lyric_score >= 2:
        return "lyrics"
    if tutorial_score >= 2:
        return "tutorial"
    return "general"


def normalize_summary_language(summary_language: str) -> str:
    summary_language = (summary_language or "").strip().lower()
    if summary_language in ("zh", "zh-tw", "traditional_chinese", "traditional chinese", "繁體中文", "中文"):
        return "zh"
    return "en"


def build_prompt(
    title: str,
    transcript: str,
    transcript_source: str,
    media_source: str,
    summary_language: str,
) -> str:
    content_type = detect_content_type(title, transcript)
    lang = normalize_summary_language(summary_language)

    if lang == "zh":
        if content_type == "finance":
            return f"""你是一個嚴謹的繁體中文整理助手。

請根據以下逐字稿，輸出「詳細版摘要」，不要過度簡化，並嚴格遵守：

【總原則】
1. 只能根據逐字稿內容整理，不要腦補。
2. 如果逐字稿有辨識錯字，請在不改變原意下，整理成自然中文。
3. 不要輸出「我不是 AI」「無法提供建議」這類廢話。
4. 如果有不確定內容，請標示「可能原文有辨識誤差」。
5. 請保留具體數字、條件、訊號、標的、觀點。
6. 請輸出繁體中文。
7. 請輸出得比一般摘要更完整，不要只有一小段。

【輸出格式】
一、主題總結
二、核心觀點
三、明確條件 / 訊號 / 數字
四、提到的標的 / 類股 / 操作方向
五、風險提醒
六、可執行整理
七、低可信度內容

標題：{title}
來源：{media_source}
文字稿來源：{transcript_source}

逐字稿：
\"\"\"
{transcript[:22000]}
\"\"\"
"""
        elif content_type == "tutorial":
            return f"""你是一個嚴謹的繁體中文整理助手。

請根據以下內容輸出詳細版教學摘要。

規則：
1. 不要腦補。
2. 不要過度簡化。
3. 把流程、步驟、條件、注意事項拆開。
4. 若逐字稿有辨識誤差，請盡量依上下文整理。
5. 不要輸出多餘免責聲明。
6. 一律使用繁體中文。

請輸出格式：
一、主題總結
二、步驟整理
三、關鍵條件 / 設定 / 數值
四、常見錯誤或注意事項
五、可直接執行清單

標題：{title}
來源：{media_source}
文字稿來源：{transcript_source}

逐字稿：
\"\"\"
{transcript[:22000]}
\"\"\"
"""
        elif content_type == "lyrics":
            return f"""你是一個嚴謹的繁體中文整理助手。

這是一份歌詞或音樂相關文字稿。請不要亂解讀成故事情節，也不要腦補過多背景。

請輸出格式：
一、內容總結
二、重複出現的主題 / 意象
三、關鍵句整理
四、可信度判斷（若文字稿疑似來自語音辨識且不完整，要直接說明）

請一律使用繁體中文。

標題：{title}
來源：{media_source}
文字稿來源：{transcript_source}

文字稿：
\"\"\"
{transcript[:22000]}
\"\"\"
"""
        else:
            return f"""你是一個嚴謹的繁體中文整理助手。

請根據下面的文字稿輸出「詳細版摘要」，不要過度簡化。

規則：
1. 不要腦補。
2. 不要輸出空泛的總結。
3. 要保留具體資訊、條件、觀點、數字。
4. 若有辨識誤差，請用最合理方式整理，但不要杜撰新資訊。
5. 若不確定，請明確說明哪部分可能不準。
6. 一律使用繁體中文。

請輸出格式：
一、主題總結
二、核心重點
三、具體資訊 / 條件 / 數字
四、可執行整理
五、低可信度內容

標題：{title}
來源：{media_source}
文字稿來源：{transcript_source}

文字稿：
\"\"\"
{transcript[:22000]}
\"\"\"
"""
    else:
        if content_type == "finance":
            return f"""You are a careful English summarization assistant.

Please produce a detailed structured summary from the transcript below.

Rules:
1. Do not invent facts.
2. Do not output generic AI disclaimers.
3. Keep concrete signals, numbers, stock names, conditions, and action logic.
4. If some transcript parts are noisy, mark them as low-confidence instead of guessing.
5. Make the summary detailed, not short.

Output format:
1. Topic Overview
2. Core Viewpoints
3. Key Conditions / Signals / Numbers
4. Mentioned Stocks / Sectors / Directions
5. Risk Conditions
6. Actionable If-Then Notes
7. Low-confidence Fragments

Title: {title}
Source: {media_source}
Transcript source: {transcript_source}

Transcript:
\"\"\"
{transcript[:22000]}
\"\"\"
"""
        else:
            return f"""You are a careful English summarization assistant.

Please produce a detailed structured summary from the transcript below.

Rules:
1. Do not invent facts.
2. Do not over-compress the summary.
3. Preserve concrete details, conditions, viewpoints, and numbers.
4. If some transcript parts are noisy, explicitly mark them as low-confidence.
5. Avoid generic filler.

Output format:
1. Topic Overview
2. Key Points
3. Concrete Details / Conditions / Numbers
4. Actionable Notes
5. Low-confidence Fragments

Title: {title}
Source: {media_source}
Transcript source: {transcript_source}

Transcript:
\"\"\"
{transcript[:22000]}
\"\"\"
"""


def summarize(
    title: str,
    transcript: str,
    transcript_source: str,
    media_source: str,
    summary_language: str,
    stop_flag,
) -> str:
    if stop_flag.get("stop"):
        raise Exception("使用者中止")

    if not shutil.which("ollama"):
        return "⚠️ Ollama is not installed." if normalize_summary_language(summary_language) == "en" else "⚠️ 未安裝 Ollama，略過摘要"

    cleaned_transcript = clean_transcript(transcript)
    prompt = build_prompt(
        title=title,
        transcript=cleaned_transcript,
        transcript_source=transcript_source,
        media_source=media_source,
        summary_language=summary_language,
    )

    process = None

    try:
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"

        process = subprocess.Popen(
            ["ollama", "run", "mistral"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        out, err = process.communicate(
            input=prompt.encode("utf-8"),
            timeout=180,
        )

        if process.returncode != 0:
            msg = err.decode("utf-8", errors="ignore").strip()
            if normalize_summary_language(summary_language) == "en":
                return f"⚠️ Summary failed: {msg or 'Unknown error'}"
            return f"⚠️ 摘要失敗：{msg or '未知錯誤'}"

        result = out.decode("utf-8", errors="ignore")
        result = re.sub(r"\n{3,}", "\n\n", result)

        if normalize_summary_language(summary_language) == "zh":
            return clean_summary(result)

        # 英文摘要不做繁簡轉換，只做基本清理
        result = result.replace("\r\n", "\n").replace("\r", "\n").strip()
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    except subprocess.TimeoutExpired:
        if process:
            process.kill()
        return "⚠️ Summary timeout" if normalize_summary_language(summary_language) == "en" else "⚠️ 摘要執行逾時"