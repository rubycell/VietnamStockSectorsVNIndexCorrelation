"""Bulk report fetcher and NotebookLM importer.

Two-phase pipeline:
1. POST /api/bulk/fetch   — scrape reports from CafeF + Vietstock for a date range
2. POST /api/bulk/import  — import un-imported reports into NotebookLM notebooks
"""

import asyncio
import logging
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Report
from app.api.reports import (
    REQUEST_HEADERS,
    VIETSTOCK_URL,
    CAFEF_URL,
    _scrape_vietstock,
    _scrape_cafef,
    _save_reports,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bulk", tags=["bulk-import"])

NOTEBOOKLM_STORAGE = Path.home() / ".notebooklm" / "storage_state.json"

# ---------------------------------------------------------------------------
# In-memory job tracking
# ---------------------------------------------------------------------------

_bulk_jobs: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class BulkFetchRequest(BaseModel):
    start_date: str  # DD/MM/YYYY format (Vietnamese date order)
    end_date: str | None = None  # defaults to today
    max_pages_per_source: int = 100


class BulkImportRequest(BaseModel):
    limit: int = 50  # max reports to import in one run
    skip_download_errors: bool = True


# ---------------------------------------------------------------------------
# Phase 1: Bulk fetch reports
# ---------------------------------------------------------------------------


def _parse_vn_date(date_str: str) -> datetime | None:
    """Parse DD/MM/YYYY date string."""
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y")
    except (ValueError, AttributeError):
        return None


def _is_before_start(report_date_str: str, start_date: datetime) -> bool:
    """Check if a report date is before the start date."""
    parsed = _parse_vn_date(report_date_str)
    if not parsed:
        return False
    return parsed < start_date


async def _fetch_vietstock_pages(
    start_date: datetime,
    end_date: datetime,
    max_pages: int,
    session: Session,
) -> dict:
    """Fetch Vietstock reports page by page until we pass start_date."""
    total_new = 0
    total_scraped = 0
    pages_fetched = 0
    errors = []
    headers = {**REQUEST_HEADERS, "Referer": "https://finance.vietstock.vn/"}

    for page in range(1, max_pages + 1):
        url = VIETSTOCK_URL if page == 1 else f"{VIETSTOCK_URL}?page={page}"
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=15.0,
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            scraped = _scrape_vietstock(response.text)
            pages_fetched += 1

            if not scraped:
                logger.info("Vietstock page %d: empty, stopping", page)
                break

            total_scraped += len(scraped)
            new_count = _save_reports(session, scraped)
            total_new += new_count

            # Check if oldest report on this page is before start_date
            dates = [r["date"] for r in scraped if r.get("date")]
            if dates:
                oldest = min(dates, key=lambda d: _parse_vn_date(d) or datetime.max)
                if _is_before_start(oldest, start_date):
                    logger.info("Vietstock page %d: reached start_date, stopping", page)
                    break

            # Rate limit
            await asyncio.sleep(2)

        except Exception as error:
            errors.append(f"Vietstock page {page}: {error}")
            logger.warning("Vietstock page %d error: %s", page, error)

    return {
        "source": "vietstock",
        "pages_fetched": pages_fetched,
        "reports_scraped": total_scraped,
        "new_reports": total_new,
        "errors": errors,
    }


async def _fetch_cafef_pages(
    start_date: datetime,
    end_date: datetime,
    max_pages: int,
    session: Session,
) -> dict:
    """Fetch CafeF reports using ASP.NET postback pagination."""
    total_new = 0
    total_scraped = 0
    pages_fetched = 0
    errors = []
    headers = {**REQUEST_HEADERS, "Referer": "https://cafef.vn/"}

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=15.0,
        ) as client:
            # Page 1: simple GET
            response = await client.get(CAFEF_URL, headers=headers)
            response.raise_for_status()
            html = response.text

            scraped = _scrape_cafef(html)
            pages_fetched += 1
            total_scraped += len(scraped)
            total_new += _save_reports(session, scraped)

            if scraped:
                dates = [r["date"] for r in scraped if r.get("date")]
                if dates:
                    oldest = min(dates, key=lambda d: _parse_vn_date(d) or datetime.max)
                    if _is_before_start(oldest, start_date):
                        return {
                            "source": "cafef",
                            "pages_fetched": pages_fetched,
                            "reports_scraped": total_scraped,
                            "new_reports": total_new,
                            "errors": errors,
                        }

            # Pages 2+: ASP.NET postback
            for page_number in range(2, max_pages + 1):
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
                    # No more pagination buttons — try next page number button
                    # CafeF only shows 3 buttons at a time, but we can POST with
                    # the page index hidden field
                    page_index_field = re.search(
                        r'name="([^"]*hdPageIndex[^"]*)"', html,
                    )
                    if not viewstate or not page_index_field:
                        logger.info("CafeF page %d: no pagination, stopping", page_number)
                        break

                    form_data = {
                        "__VIEWSTATE": viewstate.group(1),
                        page_index_field.group(1): str(page_number),
                    }
                    if viewstate_gen:
                        form_data["__VIEWSTATEGENERATOR"] = viewstate_gen.group(1)
                else:
                    form_data = {
                        "__VIEWSTATE": viewstate.group(1),
                        button_name.group(1): str(page_number),
                    }
                    if viewstate_gen:
                        form_data["__VIEWSTATEGENERATOR"] = viewstate_gen.group(1)

                await asyncio.sleep(2)

                response = await client.post(CAFEF_URL, headers=headers, data=form_data)
                response.raise_for_status()
                html = response.text

                scraped = _scrape_cafef(html)
                pages_fetched += 1

                if not scraped:
                    logger.info("CafeF page %d: empty, stopping", page_number)
                    break

                total_scraped += len(scraped)
                total_new += _save_reports(session, scraped)

                # Check dates
                dates = [r["date"] for r in scraped if r.get("date")]
                if dates:
                    oldest = min(dates, key=lambda d: _parse_vn_date(d) or datetime.max)
                    if _is_before_start(oldest, start_date):
                        logger.info("CafeF page %d: reached start_date, stopping", page_number)
                        break

    except Exception as error:
        errors.append(f"CafeF: {error}")
        logger.warning("CafeF error: %s", error)

    return {
        "source": "cafef",
        "pages_fetched": pages_fetched,
        "reports_scraped": total_scraped,
        "new_reports": total_new,
        "errors": errors,
    }


@router.post("/fetch")
async def bulk_fetch_reports(
    body: BulkFetchRequest,
    session: Session = Depends(get_database_session),
):
    """Scrape reports from both sources for a date range.

    Date format: DD/MM/YYYY (Vietnamese format).
    Example: POST /api/bulk/fetch {"start_date": "01/01/2026"}
    """
    start_date = _parse_vn_date(body.start_date)
    if not start_date:
        return {"error": f"Invalid start_date: {body.start_date}. Use DD/MM/YYYY"}

    if body.end_date:
        end_date = _parse_vn_date(body.end_date)
        if not end_date:
            return {"error": f"Invalid end_date: {body.end_date}. Use DD/MM/YYYY"}
    else:
        end_date = datetime.now()

    max_pages = min(body.max_pages_per_source, 200)

    # Fetch from both sources
    vietstock_result = await _fetch_vietstock_pages(
        start_date, end_date, max_pages, session,
    )
    cafef_result = await _fetch_cafef_pages(
        start_date, end_date, max_pages, session,
    )

    # Count total reports in date range
    total_in_db = session.query(Report).count()

    return {
        "date_range": {
            "start": body.start_date,
            "end": body.end_date or "today",
        },
        "vietstock": vietstock_result,
        "cafef": cafef_result,
        "total_reports_in_db": total_in_db,
    }


# ---------------------------------------------------------------------------
# Phase 2: Bulk import to NotebookLM
# ---------------------------------------------------------------------------


async def _download_pdf(download_url: str) -> bytes | None:
    """Download a report PDF. Returns bytes or None on failure."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0,
        ) as client:
            response = await client.get(download_url, headers=REQUEST_HEADERS)
            response.raise_for_status()
            if len(response.content) > 500:  # skip tiny error pages
                return response.content
    except Exception as error:
        logger.warning("PDF download failed for %s: %s", download_url[:80], error)
    return None


async def _download_pdfs_batch(
    reports: list,
    concurrency: int = 5,
) -> dict[str, bytes | None]:
    """Download multiple PDFs concurrently. Returns {edoc_id: bytes|None}."""
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, bytes | None] = {}

    async def _download_one(report):
        async with semaphore:
            pdf_bytes = await _download_pdf(report.download_url)
            results[report.edoc_id] = pdf_bytes
            await asyncio.sleep(0.5)  # small delay between downloads

    tasks = [_download_one(r) for r in reports]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results


def _extract_pdf_fingerprint(pdf_bytes: bytes) -> dict:
    """Extract a three-layer fingerprint from a PDF for deduplication.

    Layer 1: /Author + /CreationDate metadata (93% coverage, strongest signal)
    Layer 2: First 500 chars of page 1 text (fallback for missing metadata)
    Layer 3: File size (tiebreaker for encrypted/image PDFs)

    Returns {"metadata": str|None, "content": str|None, "size": int}
    """
    import io
    from pypdf import PdfReader

    fingerprint = {"metadata": None, "content": None, "size": len(pdf_bytes)}

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))

        # Layer 1: Metadata fingerprint
        meta = reader.metadata
        if meta:
            author = (meta.get("/Author") or "").strip()
            creation_date = (meta.get("/CreationDate") or "").strip()
            if author and creation_date:
                fingerprint["metadata"] = f"{author}|{creation_date}"

        # Layer 2: Content fingerprint (first page text)
        if reader.pages:
            first_page_text = reader.pages[0].extract_text() or ""
            normalized = " ".join(first_page_text.split())[:500]
            if len(normalized) > 50:
                fingerprint["content"] = normalized

    except Exception as error:
        logger.debug("PDF fingerprint extraction failed: %s", error)

    return fingerprint


def _is_duplicate(
    fingerprint: dict,
    existing_fingerprints: list[dict],
) -> bool:
    """Check if a PDF fingerprint matches any existing fingerprint.

    Priority: metadata > content > size.
    """
    # Layer 1: Metadata match (strongest — same author + same creation second)
    if fingerprint["metadata"]:
        for existing in existing_fingerprints:
            if existing["metadata"] and existing["metadata"] == fingerprint["metadata"]:
                return True

    # Layer 2: Content match (first 500 chars of page 1)
    if fingerprint["content"]:
        for existing in existing_fingerprints:
            if existing["content"] and existing["content"] == fingerprint["content"]:
                return True

    # Layer 3: Size match as weak signal (only if within 1% AND same notebook)
    # Not used alone — too many false positives. Only confirms when combined
    # with partial content match in future improvements.

    return False


async def _add_pdf_to_notebook(
    client,
    pdf_bytes: bytes,
    notebook_id: str,
    filename: str = "report.pdf",
) -> bool:
    """Add a PDF to an existing NotebookLM notebook using a shared client."""
    # Use a meaningful filename — NotebookLM shows it in the sources panel
    safe_name = re.sub(r"[^\w\s\-.]", "", filename)[:80] or "report"
    if not safe_name.endswith(".pdf"):
        safe_name += ".pdf"

    temp_dir = Path(tempfile.gettempdir()) / "notebooklm_import"
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / safe_name
    temp_path.write_bytes(pdf_bytes)

    try:
        # Retry up to 3 times with increasing backoff for transient errors
        for attempt in range(3):
            try:
                await client.sources.add_file(notebook_id, str(temp_path), wait=True)
                return True
            except Exception as error:
                error_msg = str(error)
                if "SOURCE_ID" in error_msg and attempt < 2:
                    backoff = 15 * (attempt + 1)  # 15s, 30s
                    logger.warning(
                        "NotebookLM retry (attempt %d/3), backing off %ds: %s",
                        attempt + 1, backoff, error_msg[:80],
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.warning("NotebookLM add_file failed: %s", error)
                return False
    finally:
        temp_path.unlink(missing_ok=True)


async def _create_notebook(client, display_name: str) -> str | None:
    """Create a new NotebookLM notebook using a shared client. Returns notebook_id."""
    try:
        notebook = await client.notebooks.create(display_name)
        return notebook.id
    except Exception as error:
        logger.warning("NotebookLM create notebook failed: %s", error)
        return None


async def _run_bulk_import(job_id: str, limit: int, skip_errors: bool) -> None:
    """Background task: import reports to NotebookLM notebooks.

    Pipeline:
    1. Group pending reports by notebook_key
    2. For each notebook group:
       a. Download all PDFs concurrently (5 at a time)
       b. Fingerprint each PDF (metadata + content + size)
       c. Dedup within the group (same report from CafeF and Vietstock)
       d. Get/create notebook in NotebookLM
       e. Upload only unique PDFs
    3. Batch commit DB updates per group (avoids SQLite locking)
    """
    from collections import defaultdict
    from app.main import SessionFactory
    from app.notebooks import (
        resolve_notebook_target,
        get_or_create_notebook_mapping,
        save_notebook_mapping,
        increment_source_count,
    )

    from notebooklm import NotebookLMClient

    job = _bulk_jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()

    storage_path = str(NOTEBOOKLM_STORAGE)
    session = SessionFactory()
    nlm_client = None
    try:
        # Single shared NotebookLM client for all uploads (avoids per-upload browser spawn)
        nlm_client = await NotebookLMClient.from_storage(path=storage_path)
        await nlm_client.__aenter__()  # activate the browser session

        # Sync DB notebook mappings with NotebookLM reality (remove stale entries)
        real_notebooks = await nlm_client.notebooks.list()
        real_notebook_ids = {nb.id for nb in real_notebooks}
        real_notebook_by_title = {nb.title: nb.id for nb in real_notebooks}
        from app.models import Notebook as NotebookModel
        db_notebooks = session.query(NotebookModel).all()
        stale_count = 0
        for db_nb in db_notebooks:
            if db_nb.notebook_id not in real_notebook_ids:
                # Check if a notebook with matching display_name exists
                matched_id = real_notebook_by_title.get(db_nb.display_name)
                if matched_id:
                    db_nb.notebook_id = matched_id
                    logger.info("Relinked %s to existing notebook %s", db_nb.display_name, matched_id)
                else:
                    session.delete(db_nb)
                    stale_count += 1
        if stale_count > 0:
            session.commit()
            logger.info("Removed %d stale notebook mappings", stale_count)

        # Get un-imported reports
        reports = (
            session.query(Report)
            .filter(Report.notebook_imported == False)  # noqa: E712
            .order_by(Report.id)
            .limit(limit)
            .all()
        )

        # Load notebook-eligible tickers: portfolio holdings + watchlist
        from app.models import Holding, WatchlistItem
        portfolio_tickers = {
            h.ticker
            for h in session.query(Holding).filter(Holding.total_shares > 0).all()
        }
        watchlist_tickers = {w.ticker for w in session.query(WatchlistItem).all()}
        notebook_tickers = portfolio_tickers | watchlist_tickers

        # Group reports by notebook_key, skipping ticker reports for unwatched stocks
        groups: dict[str, list] = defaultdict(list)
        report_routing: dict[int, tuple[str, str, str]] = {}
        skipped_unwatched = 0
        for report in reports:
            notebook_type, notebook_key, display_name = resolve_notebook_target(
                report.ticker, report.title,
            )
            if notebook_type == "ticker" and notebook_key not in notebook_tickers:
                report.notebook_imported = True
                report.notebook_key = f"SKIP:UNWATCH:{notebook_key}"
                skipped_unwatched += 1
                continue
            groups[notebook_key].append(report)
            report_routing[report.id] = (notebook_type, notebook_key, display_name)
        if skipped_unwatched:
            session.commit()
            logger.info("Skipped %d reports for unwatched tickers", skipped_unwatched)
        job["skipped_unwatched"] = skipped_unwatched

        job["total"] = len(reports)
        job["notebook_groups"] = len(groups)
        job["groups_done"] = 0

        for group_index, (notebook_key, group_reports) in enumerate(groups.items()):
            # Check for stop request between groups
            if job.get("stop_requested"):
                job["status"] = "stopped"
                logger.info("Import stopped by user at group %d/%d", group_index + 1, len(groups))
                break

            notebook_type, _, display_name = report_routing[group_reports[0].id]

            job["current_group"] = f"{display_name} ({len(group_reports)} reports)"
            logger.info(
                "Processing group %d/%d: %s (%d reports)",
                group_index + 1, len(groups), display_name, len(group_reports),
            )

            # Step 1: Get or create NotebookLM notebook (once per group)
            existing_notebook = get_or_create_notebook_mapping(
                session, notebook_type, notebook_key, display_name,
            )

            if existing_notebook:
                notebook_id = existing_notebook.notebook_id
            else:
                # Check if a notebook with this name already exists in NotebookLM
                notebook_id = real_notebook_by_title.get(display_name)
                if notebook_id:
                    existing_notebook = save_notebook_mapping(
                        session, notebook_type, notebook_key, notebook_id, display_name,
                    )
                    logger.info("Linked existing notebook '%s' → %s", display_name, notebook_id)

            if not existing_notebook:
                notebook_id = await _create_notebook(nlm_client, display_name)
                if not notebook_id:
                    job["failed"] += len(group_reports)
                    job["current"] += len(group_reports)
                    job["errors"].append(f"Failed to create notebook '{display_name}'")
                    if not skip_errors:
                        break
                    # Mark all as failed to avoid retry
                    for report in group_reports:
                        report.notebook_imported = True
                        report.notebook_key = f"FAIL:{notebook_key}"
                    session.commit()
                    continue
                existing_notebook = save_notebook_mapping(
                    session, notebook_type, notebook_key, notebook_id, display_name,
                )

            # Step 2: Download all PDFs concurrently
            pdf_data = await _download_pdfs_batch(group_reports, concurrency=5)

            # Step 3: Fingerprint and dedup
            fingerprints_seen: list[dict] = []
            uploads: list[tuple] = []  # (report, pdf_bytes)

            for report in group_reports:
                pdf_bytes = pdf_data.get(report.edoc_id)

                if not pdf_bytes:
                    job["skipped"] += 1
                    report.notebook_imported = True
                    report.notebook_key = f"SKIP:{notebook_key}"
                    continue

                fingerprint = _extract_pdf_fingerprint(pdf_bytes)

                if _is_duplicate(fingerprint, fingerprints_seen):
                    job["duplicates"] += 1
                    logger.info("Duplicate: %s in %s", report.edoc_id, display_name)
                    report.notebook_imported = True
                    report.notebook_key = f"DUP:{notebook_key}"
                    continue

                fingerprints_seen.append(fingerprint)
                uploads.append((report, pdf_bytes))

            # Step 4: Upload unique PDFs to NotebookLM (sequential — API rate limit)
            for report, pdf_bytes in uploads:
                if job.get("stop_requested"):
                    break

                job["current"] += 1
                job["current_title"] = report.title[:60]

                success = await _add_pdf_to_notebook(
                    nlm_client, pdf_bytes, notebook_id, filename=report.title,
                )
                if success:
                    report.notebook_imported = True
                    report.notebook_key = notebook_key
                    increment_source_count(session, existing_notebook)
                    job["imported"] += 1
                    logger.info(
                        "Imported %s → %s (%d total)",
                        report.edoc_id, display_name, job["imported"],
                    )
                else:
                    job["failed"] += 1
                    report.notebook_imported = True
                    report.notebook_key = f"FAIL:{notebook_key}"
                    job["errors"].append(f"Failed to upload {report.edoc_id}")
                    if not skip_errors:
                        break

                # Rate limit NotebookLM (10s between uploads to avoid rate limiting)
                await asyncio.sleep(10)

            # Step 5: Batch commit all DB changes for this group
            session.commit()
            job["groups_done"] = group_index + 1

        if job["status"] != "stopped":
            job["status"] = "completed"

    except Exception as error:
        job["status"] = "failed"
        job["error"] = str(error)
        logger.exception("Bulk import failed: %s", error)
    finally:
        job["completed_at"] = datetime.utcnow().isoformat()
        session.close()
        # Close the shared NotebookLM client (browser session)
        if nlm_client:
            try:
                await nlm_client.__aexit__(None, None, None)
            except Exception:
                pass


@router.post("/import")
async def bulk_import_to_notebooks(
    body: BulkImportRequest,
    session: Session = Depends(get_database_session),
):
    """Import un-imported reports into NotebookLM notebooks (background job).

    Each report is routed to the correct notebook:
    - Ticker reports → notebook named after the ticker (e.g., "HPG")
    - Sector reports → English sector name (e.g., "Steel Sector")
    - Strategy/Macro → "Strategy and Macroeconomic"
    """
    if not NOTEBOOKLM_STORAGE.exists():
        return {"error": "NotebookLM not logged in. Run 'notebooklm login' first."}

    pending_count = (
        session.query(Report)
        .filter(Report.notebook_imported == False)  # noqa: E712
        .count()
    )

    if pending_count == 0:
        return {"message": "No un-imported reports found.", "pending": 0}

    job_id = str(uuid.uuid4())[:8]
    _bulk_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "total": 0,
        "current": 0,
        "current_title": "",
        "imported": 0,
        "skipped": 0,
        "skipped_unwatched": 0,
        "duplicates": 0,
        "failed": 0,
        "stop_requested": False,
        "errors": [],
        "started_at": None,
        "completed_at": None,
    }

    asyncio.create_task(_run_bulk_import(job_id, body.limit, body.skip_download_errors))

    return {
        "job_id": job_id,
        "status": "pending",
        "pending_reports": pending_count,
        "limit": body.limit,
        "message": f"Import started. Poll GET /api/bulk/import/status/{job_id}",
    }


@router.get("/import/status/{job_id}")
async def get_import_status(job_id: str):
    """Check status of a bulk import job."""
    job = _bulk_jobs.get(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}
    return job


@router.post("/import/stop/{job_id}")
async def stop_import(job_id: str):
    """Request a running import job to stop after the current report."""
    job = _bulk_jobs.get(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}
    if job["status"] != "running":
        return {"error": f"Job is not running (status={job['status']})"}
    job["stop_requested"] = True
    return {"message": f"Stop requested for job {job_id}. Will stop after current report."}


@router.get("/stats")
def get_import_stats(session: Session = Depends(get_database_session)):
    """Get import statistics: how many reports imported vs pending."""
    from sqlalchemy import func

    total = session.query(Report).count()
    imported = (
        session.query(Report)
        .filter(Report.notebook_imported == True)  # noqa: E712
        .count()
    )
    pending = total - imported

    # Breakdown by notebook_key
    breakdown = (
        session.query(Report.notebook_key, func.count(Report.id))
        .filter(Report.notebook_imported == True)  # noqa: E712
        .group_by(Report.notebook_key)
        .all()
    )

    return {
        "total_reports": total,
        "imported": imported,
        "pending": pending,
        "by_notebook": {key: count for key, count in breakdown if key},
    }


@router.post("/verify-routing")
def verify_routing_with_gemini(
    sample_size: int = 20,
    session: Session = Depends(get_database_session),
):
    """Double-check report routing by classifying titles with Gemini Flash Lite.

    Compares regex-based routing against LLM classification.
    Samples reports randomly to avoid API costs on all 676.
    """
    from sqlalchemy import func as sa_func
    from app.classify_report import classify_batch

    reports = (
        session.query(Report)
        .order_by(sa_func.random())
        .limit(min(sample_size, 50))
        .all()
    )

    batch = [
        {"edoc_id": r.edoc_id, "title": r.title, "ticker": r.ticker or ""}
        for r in reports
    ]

    results = classify_batch(batch)

    matches = sum(1 for r in results if r["match"])
    mismatches = [r for r in results if not r["match"]]

    return {
        "total_checked": len(results),
        "matches": matches,
        "mismatches_count": len(mismatches),
        "accuracy": f"{matches / len(results) * 100:.1f}%" if results else "N/A",
        "mismatches": mismatches,
    }
