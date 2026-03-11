"""Unified async job system for long-running API operations.

All slow endpoints submit work as background jobs that return instantly.
Poll GET /api/jobs/{job_id} for results.

Provides job-start endpoints for each slow operation so OpenClaw skills
can use simple curl calls that always return in <1s.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

MAX_JOBS = 100
_jobs: dict[str, dict] = {}


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str  # "pending", "running", "completed", "failed"
    description: str
    result: dict | list | str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


def _prune_old_jobs() -> None:
    """Remove oldest completed/failed jobs when store exceeds MAX_JOBS."""
    if len(_jobs) <= MAX_JOBS:
        return
    completed = [
        (job_id, job) for job_id, job in _jobs.items()
        if job["status"] in ("completed", "failed")
    ]
    completed.sort(key=lambda item: item[1].get("completed_at") or "")
    for job_id, _ in completed[: len(_jobs) - MAX_JOBS]:
        del _jobs[job_id]


def _create_session():
    """Create a fresh database session for background tasks."""
    from app.main import SessionFactory
    return SessionFactory()


async def _run_job(job_id: str, work_function) -> None:
    """Execute the work function and update job status."""
    job = _jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = await work_function()
        job["status"] = "completed"
        job["result"] = result
    except Exception as error:
        job["status"] = "failed"
        job["error"] = str(error)

    job["completed_at"] = datetime.now(timezone.utc).isoformat()


def submit_job(job_type: str, work_function, description: str = "") -> dict:
    """Submit a background job. Returns immediately with job_id."""
    _prune_old_jobs()

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id": job_id,
        "job_type": job_type,
        "status": "pending",
        "description": description,
        "result": None,
        "error": None,
        "started_at": None,
        "completed_at": None,
    }

    asyncio.create_task(_run_job(job_id, work_function))

    return {
        "job_id": job_id,
        "status": "pending",
        "job_type": job_type,
        "description": description,
        "poll_url": f"/api/jobs/{job_id}",
        "message": f"Job started. Poll GET /api/jobs/{job_id} for results.",
    }


# ---------------------------------------------------------------------------
# Poll / list endpoints
# ---------------------------------------------------------------------------


@router.get("", tags=["jobs"])
async def list_jobs(
    status: str | None = None,
    limit: int = 20,
):
    """List recent jobs, optionally filtered by status."""
    jobs = list(_jobs.values())
    if status:
        jobs = [job for job in jobs if job["status"] == status]
    jobs.sort(key=lambda job: job.get("started_at") or "", reverse=True)
    return {"jobs": jobs[:limit], "total": len(jobs)}


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Check the status of a background job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobStatusResponse(**job)


# ---------------------------------------------------------------------------
# Job-start endpoints (one per slow operation)
# ---------------------------------------------------------------------------


@router.get("/start/check-cycle")
async def start_check_cycle():
    """Start a full check cycle as a background job."""
    async def do_work():
        from app.api.check_cycle import run_check_cycle
        session = _create_session()
        try:
            return run_check_cycle(session=session)
        finally:
            session.close()

    return submit_job("check-cycle", do_work, "Full check cycle: prices → portfolio → swing lows → rules")


@router.get("/start/fetch-reports")
async def start_fetch_reports():
    """Start scraping Vietstock + CafeF for new reports."""
    async def do_work():
        from app.api.reports import fetch_reports
        session = _create_session()
        try:
            return await fetch_reports(session=session)
        finally:
            session.close()

    return submit_job("fetch-reports", do_work, "Scraping Vietstock and CafeF for new reports")


@router.get("/start/fetch-prices")
async def start_fetch_prices(
    tickers: str = Query(
        ...,
        description="Comma-separated tickers (e.g. VCB,FPT,MBB)",
    ),
    days_back: int = Query(365),
):
    """Start fetching prices for given tickers."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    async def do_work():
        from app.api.prices import FetchRequest, fetch_prices
        session = _create_session()
        try:
            return fetch_prices(
                body=FetchRequest(tickers=ticker_list, days_back=days_back),
                session=session,
            )
        finally:
            session.close()

    return submit_job(
        "fetch-prices", do_work,
        f"Fetching prices for {', '.join(ticker_list)}",
    )


@router.get("/start/evaluate-rules")
async def start_evaluate_rules():
    """Start rules evaluation as a background job."""
    async def do_work():
        from app.api.rules import evaluate
        session = _create_session()
        try:
            return evaluate(session=session)
        finally:
            session.close()

    return submit_job("evaluate-rules", do_work, "Evaluating trading rules")


@router.get("/start/execute-agent/{agent_id}")
async def start_execute_agent(agent_id: str):
    """Start agent execution as a background job."""
    async def do_work():
        from app.api.agents import execute_agent, AgentExecuteRequest
        session = _create_session()
        try:
            return execute_agent(
                agent_id=agent_id,
                body=AgentExecuteRequest(),
                session=session,
            )
        finally:
            session.close()

    return submit_job(
        "execute-agent", do_work,
        f"Executing agent {agent_id}",
    )


@router.get("/start/analyze")
async def start_analyze(
    edoc_id: str = Query(..., description="Report edoc_id"),
    question: str = Query(
        "Summarize this report in Vietnamese. Include key recommendations, target prices, and reasoning.",
        description="Question to ask about the report",
    ),
):
    """Start report analysis via NotebookLM as a background job."""
    async def do_work():
        from app.api.analyze_report import (
            _download_report_pdf,
            _analyze_with_notebooklm,
        )
        from app.models import Report
        session = _create_session()
        try:
            report = session.query(Report).filter_by(edoc_id=edoc_id).first()
            if not report:
                return {"error": f"Report {edoc_id} not found"}

            pdf_bytes = await _download_report_pdf(report.download_url)
            if not pdf_bytes:
                return {"error": f"Failed to download PDF from {report.download_url}"}

            result = await _analyze_with_notebooklm(
                pdf_bytes, report.title, question,
            )
            return {
                "edoc_id": edoc_id,
                "title": report.title,
                "notebook_id": result["notebook_id"],
                "answer": result["answer"],
            }
        finally:
            session.close()

    return submit_job("analyze", do_work, f"Analyzing report {edoc_id} via NotebookLM")
