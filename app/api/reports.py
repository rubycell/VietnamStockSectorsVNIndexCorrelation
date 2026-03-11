"""Vietstock and CafeF analysis reports scraper API."""

import re
from html import unescape

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Report

router = APIRouter(prefix="/api/reports", tags=["reports"])

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

# --- Vietstock ---
VIETSTOCK_URL = "https://finance.vietstock.vn/bao-cao-phan-tich"
VIETSTOCK_BASE = "https://finance.vietstock.vn"

# --- CafeF ---
CAFEF_URL = "https://cafef.vn/du-lieu/phan-tich-bao-cao.chn"
CAFEF_CDN = "https://cafef1.mediacdn.vn/Images/Uploaded/DuLieuDownload/PhanTichBaoCao"


def _scrape_vietstock(html: str) -> list[dict]:
    """Extract report entries from Vietstock HTML."""
    reports = []
    seen_ids = set()

    for download_match in re.finditer(r'href=["\']?/downloadedoc/(\d+)', html):
        edoc_id = download_match.group(1)
        if edoc_id in seen_ids:
            continue

        download_pos = download_match.start()
        context_start = max(0, download_pos - 2000)
        context_end = min(len(html), download_pos + 200)
        context = html[context_start:context_end]

        title_matches = list(re.finditer(
            r'<a\s[^>]*class=["\']?title-link["\']?\s+href=["\']?'
            r'(/bao-cao-phan-tich/\d+/[^\s"\'>#]+)["\']?[^>]*>'
            r'([^<]+)</a>',
            context,
        ))

        if not title_matches:
            title_matches = list(re.finditer(
                r'<h3><a\s[^>]*href=["\']?'
                r'(/bao-cao-phan-tich/\d+/[^\s"\'>#]+)["\']?[^>]*>\s*'
                r'([^<]+?)\s*</a></h3>',
                context,
            ))

        if not title_matches:
            continue

        title_match = title_matches[-1]
        detail_url = title_match.group(1)
        title = unescape(title_match.group(2).strip())

        if not re.search(r'/bao-cao-phan-tich/\d+/', detail_url):
            if len(title_matches) > 1:
                title_match = title_matches[-2]
                detail_url = title_match.group(1)
                title = unescape(title_match.group(2).strip())
            else:
                continue

        seen_ids.add(edoc_id)

        date = ""
        date_match = re.search(r'<i>(\d{2}/\d{2}/\d{4})</i>', context)
        if date_match:
            date = date_match.group(1)

        source = ""
        source_match = re.search(r'<b\s+class=["\']?title["\']?>\s*([^<]+)', context)
        if source_match:
            source = source_match.group(1).strip()
        else:
            source_match = re.search(
                r'Nguồn:.*?</span>\s*<a[^>]*>([^<]+)', context, re.DOTALL,
            )
            if source_match:
                source = source_match.group(1).strip()

        thumbnail = ""
        img_match = re.search(
            r'<img[^>]+src=["\']?(https?://static1\.vietstock\.vn/edocs/[^\s"\'>#]+)',
            context,
        )
        if img_match:
            thumbnail = img_match.group(1)

        # Try to extract ticker from title (first 1-4 uppercase letters before colon/space)
        ticker = ""
        ticker_match = re.match(r'^([A-Z]{2,4})[\s:—–\-]', title)
        if ticker_match:
            ticker = ticker_match.group(1)

        reports.append({
            "edoc_id": f"vs_{edoc_id}",
            "title": title,
            "detail_url": VIETSTOCK_BASE + detail_url,
            "source": source,
            "date": date,
            "download_url": f"{VIETSTOCK_BASE}/downloadedoc/{edoc_id}",
            "thumbnail": thumbnail,
            "report_source": "vietstock",
            "ticker": ticker,
        })

    return reports


def _scrape_cafef(html: str) -> list[dict]:
    """Extract report entries from CafeF HTML.

    Each report row has: date, title link, source, ticker, download onclick.
    Download URL: DownloadBaoCao('ID', 'FILENAME', 0)
    -> https://cafef1.mediacdn.vn/Images/Uploaded/DuLieuDownload/PhanTichBaoCao/FILENAME
    """
    reports = []
    seen_ids = set()

    # Find all DownloadBaoCao calls
    for match in re.finditer(
        r"DownloadBaoCao\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*\d+\s*\)",
        html,
    ):
        cafef_id = match.group(1)
        filename = match.group(2)

        if cafef_id in seen_ids:
            continue
        seen_ids.add(cafef_id)

        download_url = f"{CAFEF_CDN}/{filename}"
        pos = match.start()
        context_start = max(0, pos - 1500)
        context_end = min(len(html), pos + 200)
        context = html[context_start:context_end]

        # Extract title from the nearest <a href="/du-lieu/report/...">
        title = ""
        detail_url = ""
        title_matches = list(re.finditer(
            r'<a\s+href="(/du-lieu/report/[^"]+)"[^>]*title="([^"]*)"',
            context,
        ))
        if not title_matches:
            title_matches = list(re.finditer(
                r'<a\s+href="(/du-lieu/report/[^"]+)"[^>]*>([^<]+)</a>',
                context,
            ))

        if title_matches:
            last_title = title_matches[-1]
            detail_url = "https://cafef.vn" + last_title.group(1)
            title = unescape(last_title.group(2).strip())

        if not title:
            continue

        # Extract date (DD/MM/YYYY)
        date = ""
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', context)
        if date_match:
            date = date_match.group(1)

        # Extract source broker - in td after the title td, contains broker abbreviation
        source = ""
        # Look for Item_Price1 cells with short uppercase broker names
        source_matches = re.findall(
            r'class="Item_Price1"[^>]*>\s*([A-Z]{2,10})\s*(?:&nbsp;)?\s*</td>',
            context,
        )
        if source_matches:
            # First match after title is the broker
            source = source_matches[0].strip()

        # Extract ticker from filename or title
        ticker = ""
        ticker_match = re.match(r'^([A-Z]{2,4})[\s:—–\-/\[]', title)
        if ticker_match:
            ticker = ticker_match.group(1)
        elif not ticker:
            # Try from filename: FRT_260304_...
            file_ticker = re.match(r'^([A-Z]{2,4})_', filename)
            if file_ticker:
                ticker = file_ticker.group(1)

        reports.append({
            "edoc_id": f"cf_{cafef_id}",
            "title": title,
            "detail_url": detail_url,
            "source": source,
            "date": date,
            "download_url": download_url,
            "thumbnail": "",
            "report_source": "cafef",
            "ticker": ticker,
        })

    return reports


def _save_reports(session: Session, reports: list[dict]) -> int:
    """Save new reports to database. Returns count of new reports added."""
    new_count = 0
    for report_data in reports:
        existing = session.query(Report).filter_by(edoc_id=report_data["edoc_id"]).first()
        if existing:
            continue
        report = Report(
            edoc_id=report_data["edoc_id"],
            title=report_data["title"],
            source=report_data["source"],
            date=report_data["date"],
            detail_url=report_data["detail_url"],
            download_url=report_data["download_url"],
            thumbnail=report_data.get("thumbnail", ""),
            report_source=report_data.get("report_source", "vietstock"),
            ticker=report_data.get("ticker", ""),
        )
        session.add(report)
        new_count += 1
    if new_count > 0:
        session.commit()
    return new_count


@router.get("")
def get_reports(
    ticker: str | None = None,
    limit: int = 20,
    session: Session = Depends(get_database_session),
):
    """Get reports from database.

    Returns a compact list by default (no URLs/thumbnails) to reduce
    token usage when called by LLM agents.  Use /api/reports/{edoc_id}
    to get full details for a specific report.
    """
    query = session.query(Report).order_by(Report.id.desc())
    if ticker:
        query = query.filter(Report.ticker == ticker.upper())
    reports = query.limit(min(limit, 50)).all()
    return {
        "reports": [
            {
                "edoc_id": r.edoc_id,
                "title": r.title,
                "source": r.source,
                "date": r.date,
                "ticker": getattr(r, "ticker", ""),
            }
            for r in reports
        ],
        "count": len(reports),
    }


@router.get("/{edoc_id}")
def get_report_detail(edoc_id: str, session: Session = Depends(get_database_session)):
    """Get full report details including URLs."""
    report = session.query(Report).filter_by(edoc_id=edoc_id).first()
    if not report:
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    return {
        "edoc_id": report.edoc_id,
        "title": report.title,
        "source": report.source,
        "date": report.date,
        "detail_url": report.detail_url,
        "download_url": report.download_url,
        "thumbnail": report.thumbnail,
        "report_source": getattr(report, "report_source", "vietstock"),
        "ticker": getattr(report, "ticker", ""),
    }


async def _fetch_cafef_pages(
    cafef_pages: int,
    session: Session,
) -> tuple[int, list[str]]:
    """Fetch multiple pages from CafeF using ASP.NET postback pagination.

    Returns (new_count, errors).
    """
    total_new = 0
    errors = []
    cafef_headers = {**REQUEST_HEADERS, "Referer": "https://cafef.vn/"}

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=15.0,
        ) as client:
            # Page 1: simple GET
            response = await client.get(CAFEF_URL, headers=cafef_headers)
            response.raise_for_status()
            html = response.text

            scraped = _scrape_cafef(html)
            total_new += _save_reports(session, scraped)

            # Pages 2+: ASP.NET postback with __VIEWSTATE
            for page_number in range(2, cafef_pages + 1):
                viewstate = re.search(
                    r'__VIEWSTATE["\s][^>]*value="([^"]+)"', html,
                )
                viewstate_gen = re.search(
                    r'__VIEWSTATEGENERATOR["\s][^>]*value="([^"]+)"', html,
                )
                button_name = re.search(
                    r'name="([^"]*btnpage[^"]*)"[^>]*value="'
                    + str(page_number) + '"',
                    html,
                )

                if not viewstate or not button_name:
                    break  # No more pages available

                form_data = {
                    "__VIEWSTATE": viewstate.group(1),
                    button_name.group(1): str(page_number),
                }
                if viewstate_gen:
                    form_data["__VIEWSTATEGENERATOR"] = viewstate_gen.group(1)

                response = await client.post(
                    CAFEF_URL, headers=cafef_headers, data=form_data,
                )
                response.raise_for_status()
                html = response.text

                scraped = _scrape_cafef(html)
                if not scraped:
                    break  # Empty page, stop
                total_new += _save_reports(session, scraped)

    except Exception as error:
        errors.append(f"CafeF: {error}")

    return total_new, errors


@router.post("/fetch")
async def fetch_reports(
    cafef_pages: int = 3,
    vietstock_pages: int = 3,
    session: Session = Depends(get_database_session),
):
    """Scrape latest reports from both Vietstock and CafeF, save new ones.

    Args:
        cafef_pages: Number of CafeF pages to scrape (default 3, max 20).
        vietstock_pages: Number of Vietstock pages to scrape (default 3, max 20).
    """
    cafef_pages = min(max(cafef_pages, 1), 20)
    vietstock_pages = min(max(vietstock_pages, 1), 20)

    total_new = 0
    errors = []

    # --- Vietstock ---
    vietstock_headers = {**REQUEST_HEADERS, "Referer": "https://finance.vietstock.vn/"}
    for page in range(1, vietstock_pages + 1):
        url = VIETSTOCK_URL if page == 1 else f"{VIETSTOCK_URL}?page={page}"
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=15.0
            ) as client:
                response = await client.get(url, headers=vietstock_headers)
                response.raise_for_status()
            scraped = _scrape_vietstock(response.text)
            new_count = _save_reports(session, scraped)
            total_new += new_count
        except Exception as error:
            errors.append(f"Vietstock page {page}: {error}")

    # --- CafeF (multi-page with ASP.NET postback) ---
    cafef_new, cafef_errors = await _fetch_cafef_pages(cafef_pages, session)
    total_new += cafef_new
    errors.extend(cafef_errors)

    return {
        "new_reports": total_new,
        "errors": errors if errors else None,
    }
