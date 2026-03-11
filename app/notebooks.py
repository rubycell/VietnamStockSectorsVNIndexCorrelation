"""Notebook routing — determines which NotebookLM notebook a report belongs to.

Each report is routed to either a ticker notebook or a category notebook:
- If the report has a ticker (e.g. HPG, FRT), it goes to the ticker notebook.
- Otherwise, title patterns determine the category notebook.
"""

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Notebook

# ---------------------------------------------------------------------------
# Report categories (Vietnamese title patterns)
# ---------------------------------------------------------------------------

CATEGORY_PATTERNS = [
    ("chien_luoc", re.compile(
        r"chiến lược|strategy|investment strategy", re.IGNORECASE,
    ), "Chiến lược"),
    ("chuyen_de", re.compile(
        r"chuyên đề|thematic|sector report", re.IGNORECASE,
    ), "Chuyên đề"),
    ("thi_truong", re.compile(
        r"báo cáo thị trường|market report|thị trường|nhận định thị trường|"
        r"morning brief|daily market|bản tin", re.IGNORECASE,
    ), "Thị trường"),
    ("vi_mo", re.compile(
        r"vĩ mô|macro|kinh tế vĩ mô|macroeconomic", re.IGNORECASE,
    ), "Vĩ mô"),
    ("nganh", re.compile(
        r"báo cáo ngành|sector|industry report|ngành", re.IGNORECASE,
    ), "Ngành"),
    ("ket_qua_kinh_doanh", re.compile(
        r"kết quả kinh doanh|earnings|lợi nhuận|revenue|doanh thu", re.IGNORECASE,
    ), "Kết quả kinh doanh"),
]


def detect_report_category(title: str) -> tuple[str, str]:
    """Detect report category from title.

    Returns (category_key, display_name).
    Falls back to "general" if no pattern matches.
    """
    for category_key, pattern, display_name in CATEGORY_PATTERNS:
        if pattern.search(title):
            return category_key, display_name

    return "general", "Tổng hợp"


def resolve_notebook_target(
    ticker: str | None,
    title: str,
) -> tuple[str, str, str]:
    """Determine which notebook a report should go into.

    Returns (notebook_type, notebook_key, display_name).
    """
    if ticker and len(ticker) >= 2:
        return "ticker", ticker.upper(), f"Ticker: {ticker.upper()}"

    category_key, category_display = detect_report_category(title)
    return "category", category_key, f"Danh mục: {category_display}"


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
