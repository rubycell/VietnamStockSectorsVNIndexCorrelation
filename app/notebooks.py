"""Notebook routing — determines which NotebookLM notebook a report belongs to.

Routing priority:
1. Stock-specific (has ticker) → notebook named after the ticker: "HPG", "FPT"
2. Sector report → English sector name: "Steel Sector", "Banking Sector", etc.
3. Strategy or macro → "Strategy and Macroeconomic"
4. General fallback → "General Reports"
"""

import re
import unicodedata
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Notebook

# ---------------------------------------------------------------------------
# Sector detection (Vietnamese title → English sector name)
# ---------------------------------------------------------------------------

SECTOR_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("steel", re.compile(
        r"thép|tôn mạ|steel|hoa sen|hòa phát|nam kim",
        re.IGNORECASE,
    ), "Steel Sector"),
    ("banking", re.compile(
        r"ngân hàng|bank|tín dụng|credit|NIM\b",
        re.IGNORECASE,
    ), "Banking Sector"),
    ("real_estate", re.compile(
        r"bất động sản|BĐS|real estate|property|nhà ở|khu công nghiệp|KCN",
        re.IGNORECASE,
    ), "Real Estate Sector"),
    ("securities", re.compile(
        r"chứng khoán|securities|brokerage",
        re.IGNORECASE,
    ), "Securities Sector"),
    ("oil_gas", re.compile(
        r"dầu khí|oil|gas|xăng dầu|petroleum|khí đốt",
        re.IGNORECASE,
    ), "Oil and Gas Sector"),
    ("power", re.compile(
        r"ngành điện|nhiệt điện|thủy điện|điện gió|điện mặt trời|power|electricity|utilities|"
        r"^Điện\b|cung cầu điện|năng lượng|năng lượng tái tạo|renewable|energy",
        re.IGNORECASE,
    ), "Power and Utilities Sector"),
    ("construction", re.compile(
        r"xây dựng|construction|vật liệu xây dựng|xi măng|cement",
        re.IGNORECASE,
    ), "Construction Sector"),
    ("retail", re.compile(
        r"bán lẻ|retail|tiêu dùng|consumer|FMCG",
        re.IGNORECASE,
    ), "Retail and Consumer Sector"),
    ("technology", re.compile(
        r"công nghệ|technology|tech|phần mềm|software|IT\b|viễn thông|telecom",
        re.IGNORECASE,
    ), "Technology Sector"),
    ("agriculture", re.compile(
        r"nông nghiệp|agriculture|thủy sản|seafood|cá tra|tôm|cao su|rubber|"
        r"phân bón|fertilizer|đường|sugar",
        re.IGNORECASE,
    ), "Agriculture Sector"),
    ("logistics", re.compile(
        r"logistics|vận tải|cảng|port|hàng không|aviation|shipping",
        re.IGNORECASE,
    ), "Logistics Sector"),
    ("textile", re.compile(
        r"dệt may|textile|garment|sợi",
        re.IGNORECASE,
    ), "Textile Sector"),
    ("insurance", re.compile(
        r"bảo hiểm|insurance",
        re.IGNORECASE,
    ), "Insurance Sector"),
    ("dairy", re.compile(
        r"sữa|dairy|milk",
        re.IGNORECASE,
    ), "Dairy Sector"),
    ("chemicals", re.compile(
        r"hóa chất|chemical|phốt pho|phosphorus|ngành nhựa|plastics",
        re.IGNORECASE,
    ), "Chemicals Sector"),
    ("healthcare", re.compile(
        r"y tế|dược|pharmaceutical|healthcare|bệnh viện|hospital",
        re.IGNORECASE,
    ), "Healthcare Sector"),
]

# Strategy + macro patterns → combined notebook
STRATEGY_MACRO_PATTERN = re.compile(
    r"chiến lược|strategy|vĩ mô|macro|macroeconomic|kinh tế vĩ mô|"
    r"investment strategy|market outlook|triển vọng thị trường|"
    r"nhận định thị trường|morning brief|daily market|bản tin thị trường|"
    r"báo cáo thị trường|market report|trung đông|middle east|"
    r"GDP|CPI|inflation|lạm phát|"
    r"triển vọng\b|hàng hóa|đầu tư đa kênh|đầu tư tháng|ý tưởng.*đầu tư|"
    r"nâng hạng|quản trị|xung đột|ETF.*dự báo|nhìn lại.*bứt phá|"
    r"tín nhiệm|TTCK|thị trường bạc|thị trường vàng|ngành nước|"
    r"đầu tư công|thương mại tự do|KQKD quý|rút ròng|ETF Việt|"
    r"cuộc chiến|kịch bản.*VNINDEX|BCCL\b|"
    r"bản tin ETF|báo cáo ETF",
    re.IGNORECASE,
)

STRATEGY_MACRO_KEY = "strategy_macro"
STRATEGY_MACRO_DISPLAY = "Strategy and Macroeconomic"

# Forex/Currency market reports
FOREX_PATTERN = re.compile(
    r"tiền tệ|forex|tỷ giá|exchange rate|ngoại hối|foreign exchange|"
    r"thị trường tiền tệ|money market|currency",
    re.IGNORECASE,
)
FOREX_KEY = "forex"
FOREX_DISPLAY = "Forex and Currency"

# Bond market reports
BOND_PATTERN = re.compile(
    r"trái phiếu|bond|TPDN|corporate bond|government bond|"
    r"thị trường trái phiếu|fixed income",
    re.IGNORECASE,
)
BOND_KEY = "bond"
BOND_DISPLAY = "Bond Market"


def detect_sector(title: str) -> tuple[str, str] | None:
    """Detect sector from title. Returns (sector_key, display_name) or None."""
    for sector_key, pattern, display_name in SECTOR_PATTERNS:
        if pattern.search(title):
            return sector_key, display_name
    return None


# Vietnamese report type abbreviations and broker-only names that are NOT stock tickers.
# Note: SSI, MBS, VCI, SHS, TPS, AGR, BSC, HSC, PSI, ABS, VDS are BOTH broker names
# AND real listed stocks — they are NOT excluded here because when they appear in
# titles it's usually about the stock itself.
NOT_TICKERS = {
    # Vietnamese report type abbreviations (e.g. BCVM = "Báo cáo vĩ mô")
    "BCVM", "BCCL", "BCPT", "BCDT", "BCTC", "BCTH", "BCTD", "BCTV",
    # Broker-only names (not listed on any exchange)
    "KBSV", "ORS", "FNS", "MAS",
    "VCBS", "VNDS", "FPTS", "BVSC", "ACBS",
    # Vietnamese abbreviations that look like tickers but aren't
    "ETF", "BDS",
}


def _extract_ticker_from_title(title: str) -> str:
    """Try to extract a stock ticker from the report title.

    Vietnamese tickers are 3 characters (e.g. VCB, HPG, NT2).
    All patterns require 3+ chars to avoid matching Vietnamese word fragments
    like BC (Báo cáo), NH (Ngân hàng), BDS (Bất động sản).
    """
    patterns = [
        # "KBC: Khuyến nghị MUA...", "[ACB/MUA +26.9%/...]", "HT1 – Cập nhật"
        r"^\[?([A-Z][A-Z0-9]{2,3})[/\s:—–\-\[\]]",
        # "HPG_Trở lại quỹ đạo", "POW_Báo cáo cập nhật"
        r"^([A-Z][A-Z0-9]{2,3})_",
        # "cổ phiếu VDS", "cổ phiếu FRT"
        r"cổ phiếu\s+([A-Z][A-Z0-9]{2,3})\b",
        # "doanh nghiệp KBC", "doanh nghiệp SZC"
        r"doanh nghiệp\s+([A-Z][A-Z0-9]{2,3})\b",
        # "Lựa chọn của tuần DCM - EVS"
        r"tuần\s+([A-Z][A-Z0-9]{2,3})\s*[-–]",
        # "...Q4/2025 – NT2 – LNST..." (ticker between dashes/em-dashes)
        r"[–—-]\s*([A-Z][A-Z0-9]{2,3})\s*[–—-]",
        # Ticker at the end of title
        r"\s([A-Z][A-Z0-9]{2,3})\s*$",
        # Ticker after double space
        r"\s{2,}([A-Z][A-Z0-9]{2,3})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, title)
        if match and match.group(1) not in NOT_TICKERS:
            return match.group(1)

    return ""


def resolve_notebook_target(
    ticker: str | None,
    title: str,
) -> tuple[str, str, str]:
    """Determine which notebook a report should go into.

    Returns (notebook_type, notebook_key, display_name).

    Routing priority:
    1. Has ticker (from scraper or title extraction) → ticker notebook
    2. Matches sector keywords → sector notebook (e.g., "Steel Sector")
    3. Matches strategy/macro → "Strategy and Macroeconomic"
    4. Fallback → "General Reports"
    """
    # Normalize Vietnamese Unicode (some sources use NFD decomposed forms)
    title = unicodedata.normalize("NFC", title)

    # 1. Stock-specific reports — use provided ticker or try extracting from title
    effective_ticker = ticker if (ticker and len(ticker) >= 3) else ""
    if not effective_ticker:
        effective_ticker = _extract_ticker_from_title(title)

    if effective_ticker and len(effective_ticker) >= 3:
        return "ticker", effective_ticker.upper(), effective_ticker.upper()

    # 2. Sector reports (check before strategy/macro since sector is more specific)
    sector = detect_sector(title)
    if sector:
        sector_key, display_name = sector
        return "sector", sector_key, display_name

    # 3. Specialized market categories (before broad strategy/macro)
    if FOREX_PATTERN.search(title):
        return "category", FOREX_KEY, FOREX_DISPLAY

    if BOND_PATTERN.search(title):
        return "category", BOND_KEY, BOND_DISPLAY

    # 4. Strategy and macroeconomic reports
    if STRATEGY_MACRO_PATTERN.search(title):
        return "category", STRATEGY_MACRO_KEY, STRATEGY_MACRO_DISPLAY

    # 4. Fallback
    return "category", "general", "General Reports"


# ---------------------------------------------------------------------------
# Notebook lookup / creation
# ---------------------------------------------------------------------------


def get_or_create_notebook_mapping(
    session: Session,
    notebook_type: str,
    notebook_key: str,
    display_name: str,
) -> Notebook | None:
    """Look up an existing notebook mapping. Returns None if not found."""
    return (
        session.query(Notebook)
        .filter_by(notebook_type=notebook_type, notebook_key=notebook_key)
        .first()
    )


def save_notebook_mapping(
    session: Session,
    notebook_type: str,
    notebook_key: str,
    notebook_id: str,
    display_name: str,
) -> Notebook:
    """Save a new notebook mapping to the database."""
    notebook = Notebook(
        notebook_type=notebook_type,
        notebook_key=notebook_key,
        notebook_id=notebook_id,
        display_name=display_name,
        source_count=1,
    )
    session.add(notebook)
    session.commit()
    return notebook


def increment_source_count(session: Session, notebook: Notebook) -> None:
    """Update source count and last_used timestamp."""
    notebook.source_count = (notebook.source_count or 0) + 1
    notebook.last_used_at = datetime.utcnow()
    session.commit()
