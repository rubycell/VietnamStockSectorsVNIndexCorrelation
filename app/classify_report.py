"""LLM-based report classification using Gemini Flash Lite.

Used as a double-check against the regex-based routing in app/notebooks.py.
The classification prompt is auto-generated from the actual routing code,
so it stays in sync with our regex patterns, NOT_TICKERS list, and sector definitions.
"""

import json
import logging
import os
import unicodedata

from google import genai

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def _build_classification_prompt() -> str:
    """Build the classification prompt from our actual routing code.

    This ensures the LLM uses the same rules as our regex router.
    """
    from app.notebooks import SECTOR_PATTERNS, STRATEGY_MACRO_PATTERN, NOT_TICKERS

    # Extract human-readable sector keywords from compiled regex patterns
    sector_descriptions = []
    for sector_key, pattern, display_name in SECTOR_PATTERNS:
        # Get the raw pattern string and clean it up for readability
        raw = pattern.pattern
        keywords = [kw.strip() for kw in raw.split("|") if kw.strip()]
        # Remove regex syntax for human readability
        clean_keywords = [
            kw.replace(r"\b", "").replace("^", "").strip()
            for kw in keywords
            if not kw.startswith("(") and len(kw) > 1
        ]
        sector_descriptions.append(
            f"   - **{display_name}**: keywords = {', '.join(clean_keywords[:8])}"
        )

    # Extract macro keywords
    macro_raw = STRATEGY_MACRO_PATTERN.pattern
    macro_keywords = [
        kw.strip().replace(r"\b", "").replace("^", "").strip()
        for kw in macro_raw.split("|")
        if kw.strip() and len(kw.strip()) > 2 and ".*" not in kw
    ]

    not_tickers_str = ", ".join(sorted(NOT_TICKERS))

    return f"""\
You are a Vietnamese stock market report classifier. Given a report title (often in Vietnamese),
classify it into exactly ONE category.

## Categories (in priority order)

### 1. TICKER — report about a specific listed stock
Extract the ticker symbol (2-4 uppercase letters/digits: HPG, FPT, NT2, VCB, KLB).
Ticker can appear anywhere in the title:
- At start: "KBC: Khuyến nghị MUA", "HPG_Trở lại quỹ đạo"
- In brackets: "[ACB/MUA +26.9%/...]"
- After Vietnamese keywords: "cổ phiếu FRT", "doanh nghiệp KBC"
- At end: "Báo cáo cập nhật KQKD Q4.2025 CTG", "Báo cáo nhanh DCM"
- After "tuần" (weekly pick): "Lựa chọn của tuần FPT - EVS" → ticker is FPT, not EVS

**NOT tickers** (these are report type abbreviations or broker-only names):
{not_tickers_str}

However, SSI, MBS, VCI, SHS, VDS are BOTH broker names AND real listed stocks —
treat them as tickers when the report is clearly about that company's stock.

### 2. SECTOR — report covers an entire industry sector
Return the exact English sector name. Available sectors and their Vietnamese keyword triggers:
{chr(10).join(sector_descriptions)}

### 3. STRATEGY_MACRO — market strategy, macroeconomics, multi-sector overview
Trigger keywords: {', '.join(macro_keywords[:20])}
Also includes: ETF analysis, geopolitical events, market outlook, investment ideas,
interest rate/exchange rate analysis, GDP/CPI data, market commentary (nhận định/bản tin thị trường).

### 4. GENERAL — only if none of the above categories fit

## Rules
- Choose the MOST SPECIFIC category: TICKER > SECTOR > STRATEGY_MACRO > GENERAL
- If a report mentions both a ticker AND a sector, prefer TICKER (it's about that specific stock)
- "Báo cáo Thị trường Tiền tệ" (money market) → STRATEGY_MACRO, not TICKER
- "KIENLONGBANK" is the full name of ticker KLB
- Multi-stock or broad market reports → STRATEGY_MACRO

## Output format
Respond with ONLY a valid JSON object (no markdown fences):
{{{{"category": "TICKER", "value": "HPG"}}}}
{{{{"category": "SECTOR", "value": "Real Estate Sector"}}}}
{{{{"category": "STRATEGY_MACRO", "value": null}}}}
{{{{"category": "GENERAL", "value": null}}}}

Title: {{title}}"""


# Cache the prompt since it's built from module-level constants
_CACHED_PROMPT: str | None = None


def _get_prompt() -> str:
    global _CACHED_PROMPT
    if _CACHED_PROMPT is None:
        _CACHED_PROMPT = _build_classification_prompt()
    return _CACHED_PROMPT


def classify_with_gemini(title: str) -> dict:
    """Classify a single report title using Gemini 3.1 Flash Lite.

    Returns {"category": "TICKER"|"SECTOR"|"STRATEGY_MACRO"|"GENERAL", "value": str|None}
    """
    if not GEMINI_API_KEY:
        return {"category": "UNKNOWN", "value": None, "error": "No GEMINI_API_KEY"}

    title = unicodedata.normalize("NFC", title)

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = _get_prompt().format(title=title)

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
        if text.startswith("json"):
            text = text[4:].strip()

        result = json.loads(text)
        return result
    except Exception as error:
        logger.warning("Gemini classification failed for '%s': %s", title[:50], error)
        return {"category": "ERROR", "value": None, "error": str(error)}


def classify_batch(titles: list[dict]) -> list[dict]:
    """Classify multiple reports and compare with regex routing.

    Input: list of {"edoc_id": str, "title": str, "ticker": str|None}
    Returns: list of {"edoc_id", "title", "regex_result", "gemini_result", "match": bool}
    """
    from app.notebooks import resolve_notebook_target

    results = []
    for item in titles:
        title = item["title"]
        ticker = item.get("ticker", "")

        # Regex-based routing
        regex_type, regex_key, regex_display = resolve_notebook_target(ticker, title)
        regex_result = {
            "type": regex_type,
            "key": regex_key,
            "display": regex_display,
        }

        # Gemini classification
        gemini_result = classify_with_gemini(title)

        # Compare results
        match = _compare_results(regex_result, gemini_result)

        results.append({
            "edoc_id": item.get("edoc_id", ""),
            "title": title[:80],
            "regex": regex_result,
            "gemini": gemini_result,
            "match": match,
        })

    return results


def _compare_results(regex_result: dict, gemini_result: dict) -> bool:
    """Check if regex and Gemini classifications agree."""
    gemini_category = gemini_result.get("category", "")
    gemini_value = (gemini_result.get("value") or "").upper()

    regex_type = regex_result["type"]
    regex_key = regex_result["key"].upper()

    if gemini_category == "TICKER" and regex_type == "ticker":
        return gemini_value == regex_key
    if gemini_category == "SECTOR" and regex_type == "sector":
        return True  # Sector name might differ slightly
    if gemini_category == "STRATEGY_MACRO" and regex_key == "STRATEGY_MACRO":
        return True
    if gemini_category == "GENERAL" and regex_key == "GENERAL":
        return True

    return False
