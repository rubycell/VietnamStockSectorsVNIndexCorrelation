"""Analyze Vietstock reports using Google NotebookLM.

Supports both sync and async (job-based) analysis:
- POST /api/analyze → starts background job, returns job_id immediately
- GET /api/analyze/status/{job_id} → poll for results
- POST /api/analyze/sync → blocks until complete (legacy)
"""

import asyncio
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Report

router = APIRouter(prefix="/api/analyze", tags=["analyze"])

NOTEBOOKLM_STORAGE = Path.home() / ".notebooklm" / "storage_state.json"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    edoc_id: str
    question: str = "Summarize this report in Vietnamese. Include key recommendations, target prices, and reasoning."


class AnalyzeResponse(BaseModel):
    edoc_id: str
    title: str
    notebook_id: str
    answer: str
    error: str | None = None


class JobSubmittedResponse(BaseModel):
    job_id: str
    status: str
    edoc_id: str
    title: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # "pending", "running", "completed", "failed"
    edoc_id: str
    title: str
    answer: str | None = None
    notebook_id: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _download_report_pdf(download_url: str) -> bytes | None:
    """Download report PDF from Vietstock."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0
        ) as client:
            response = await client.get(download_url, headers=REQUEST_HEADERS)
            response.raise_for_status()
            if len(response.content) > 0:
                return response.content
    except Exception:
        pass
    return None


async def _analyze_with_notebooklm(
    pdf_bytes: bytes,
    title: str,
    question: str,
    existing_notebook_id: str | None = None,
    notebook_display_name: str | None = None,
) -> dict:
    """Add PDF to a NotebookLM notebook and ask a question.

    If existing_notebook_id is provided, adds the PDF as a new source to that
    notebook (multi-source context). Otherwise creates a new notebook.

    Returns {"notebook_id": ..., "answer": ..., "created_new": bool}.
    """
    from notebooklm import NotebookLMClient

    storage_path = str(NOTEBOOKLM_STORAGE)
    if not NOTEBOOKLM_STORAGE.exists():
        raise FileNotFoundError(
            "NotebookLM credentials not found. Run 'notebooklm login' first."
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_file.write(pdf_bytes)
        temp_path = temp_file.name

    created_new = False
    try:
        async with await NotebookLMClient.from_storage(path=storage_path) as client:
            if existing_notebook_id:
                notebook_id = existing_notebook_id
            else:
                display = notebook_display_name or f"Report: {title[:80]}"
                notebook = await client.notebooks.create(display)
                notebook_id = notebook.id
                created_new = True

            await client.sources.add_file(
                notebook_id, temp_path, wait=True,
            )

            result = await client.chat.ask(notebook_id, question)

            return {
                "notebook_id": notebook_id,
                "answer": result.answer,
                "created_new": created_new,
            }
    finally:
        Path(temp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Background job runner
# ---------------------------------------------------------------------------


async def _run_analysis_job(job_id: str, report: dict, question: str) -> None:
    """Run analysis in the background and update the job store.

    Routes the report to the appropriate persistent notebook (by ticker or
    category) so that context accumulates across multiple reports.
    """
    from app.main import SessionFactory
    from app.notebooks import (
        resolve_notebook_target,
        get_or_create_notebook_mapping,
        save_notebook_mapping,
        increment_source_count,
    )

    job = _jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        pdf_bytes = await _download_report_pdf(report["download_url"])
        if not pdf_bytes:
            job["status"] = "failed"
            job["error"] = f"Failed to download PDF from {report['download_url']}"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            return

        # Resolve which notebook this report belongs to
        notebook_type, notebook_key, display_name = resolve_notebook_target(
            report.get("ticker"), report["title"],
        )

        db_session = SessionFactory()
        try:
            existing = get_or_create_notebook_mapping(
                db_session, notebook_type, notebook_key, display_name,
            )
            existing_notebook_id = existing.notebook_id if existing else None

            result = await _analyze_with_notebooklm(
                pdf_bytes,
                report["title"],
                question,
                existing_notebook_id=existing_notebook_id,
                notebook_display_name=display_name,
            )

            # Save new mapping or update source count
            if result["created_new"]:
                save_notebook_mapping(
                    db_session, notebook_type, notebook_key,
                    result["notebook_id"], display_name,
                )
            elif existing:
                increment_source_count(db_session, existing)

            job["status"] = "completed"
            job["answer"] = result["answer"]
            job["notebook_id"] = result["notebook_id"]
            job["notebook_type"] = notebook_type
            job["notebook_key"] = notebook_key
        finally:
            db_session.close()

    except Exception as error:
        job["status"] = "failed"
        job["error"] = str(error)

    job["completed_at"] = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Async endpoints (preferred — job-based)
# ---------------------------------------------------------------------------


@router.post("", response_model=JobSubmittedResponse)
async def submit_analysis(
    request: AnalyzeRequest,
    session: Session = Depends(get_database_session),
):
    """Start analysis as a background job. Returns job_id immediately."""
    report = session.query(Report).filter_by(edoc_id=request.edoc_id).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {request.edoc_id} not found")

    job_id = str(uuid.uuid4())[:8]

    # Store report data for the background task (session won't be available)
    report_data = {
        "title": report.title,
        "download_url": report.download_url,
    }

    _jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "edoc_id": request.edoc_id,
        "title": report.title,
        "answer": None,
        "notebook_id": None,
        "error": None,
        "started_at": None,
        "completed_at": None,
    }

    # Fire and forget — runs in the background
    asyncio.create_task(_run_analysis_job(job_id, report_data, request.question))

    return JobSubmittedResponse(
        job_id=job_id,
        status="pending",
        edoc_id=request.edoc_id,
        title=report.title,
        message=f"Analysis started. Poll GET /api/analyze/status/{job_id} for results.",
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_analysis_status(job_id: str):
    """Check the status of an analysis job. Returns results when completed."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(**job)


@router.get("/jobs")
async def list_jobs():
    """List all analysis jobs (recent first)."""
    jobs = sorted(
        _jobs.values(),
        key=lambda job: job.get("started_at") or "",
        reverse=True,
    )
    return {"jobs": jobs[:20], "total": len(_jobs)}


# ---------------------------------------------------------------------------
# Sync endpoint (legacy — blocks until complete)
# ---------------------------------------------------------------------------


@router.post("/sync", response_model=AnalyzeResponse)
async def analyze_report_sync(
    request: AnalyzeRequest,
    session: Session = Depends(get_database_session),
):
    """Analyze a report synchronously. Blocks for 30-60s. Use POST /api/analyze for async."""
    report = session.query(Report).filter_by(edoc_id=request.edoc_id).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {request.edoc_id} not found")

    pdf_bytes = await _download_report_pdf(report.download_url)
    if not pdf_bytes:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to download PDF from {report.download_url}",
        )

    try:
        result = await _analyze_with_notebooklm(
            pdf_bytes, report.title, request.question,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"NotebookLM error: {error}")

    return AnalyzeResponse(
        edoc_id=request.edoc_id,
        title=report.title,
        notebook_id=result["notebook_id"],
        answer=result["answer"],
    )


# ---------------------------------------------------------------------------
# Notebook management
# ---------------------------------------------------------------------------


@router.get("/notebooks")
async def list_notebooks(
    session: Session = Depends(get_database_session),
):
    """List all notebook mappings (local DB) with optional remote sync."""
    from app.models import Notebook as NotebookModel

    mappings = (
        session.query(NotebookModel)
        .order_by(NotebookModel.notebook_type, NotebookModel.notebook_key)
        .all()
    )

    return {
        "notebooks": [
            {
                "notebook_type": nb.notebook_type,
                "notebook_key": nb.notebook_key,
                "notebook_id": nb.notebook_id,
                "display_name": nb.display_name,
                "source_count": nb.source_count,
                "created_at": nb.created_at.isoformat() if nb.created_at else None,
                "last_used_at": nb.last_used_at.isoformat() if nb.last_used_at else None,
            }
            for nb in mappings
        ],
        "count": len(mappings),
        "ticker_notebooks": sum(1 for nb in mappings if nb.notebook_type == "ticker"),
        "category_notebooks": sum(1 for nb in mappings if nb.notebook_type == "category"),
    }


@router.get("/notebooks/remote")
async def list_remote_notebooks():
    """List all NotebookLM notebooks from the remote API (for debugging)."""
    from notebooklm import NotebookLMClient

    if not NOTEBOOKLM_STORAGE.exists():
        raise HTTPException(status_code=503, detail="NotebookLM not logged in")

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        notebooks = await client.notebooks.list()
        return {
            "notebooks": [
                {"id": nb.id, "title": nb.title}
                for nb in notebooks
            ],
            "count": len(notebooks),
        }
