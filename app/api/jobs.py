"""Unified async job system for long-running API operations.

All slow endpoints submit work as background jobs that return instantly.
Poll GET /api/jobs/{job_id} for results.

Provides job-start endpoints for each slow operation so OpenClaw skills
can use simple curl calls that always return in <1s.

When notify=true, completed jobs push results to the user via OpenClaw's
webhook API (/hooks/agent), so the bot formats and delivers them.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

MAX_JOBS = 100
_jobs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Deduplication cooldown — prevents re-submitting the same job within a window
# Key: "job_type:dedup_key" → {"job_id": str, "submitted_at": datetime, "status": str}
# ---------------------------------------------------------------------------

DEDUP_COOLDOWN_SECONDS = 180  # 3 minutes
_recent_submissions: dict[str, dict] = {}


def _check_dedup(job_type: str, dedup_key: str | None) -> dict | None:
    """Return the existing job if an identical one was submitted within the cooldown window.

    Returns None if no duplicate found (caller should proceed with new job).
    Returns the existing job dict if a recent duplicate exists.
    """
    if not dedup_key:
        return None

    cache_key = f"{job_type}:{dedup_key}"
    entry = _recent_submissions.get(cache_key)
    if not entry:
        return None

    elapsed = (datetime.now(timezone.utc) - entry["submitted_at"]).total_seconds()
    if elapsed > DEDUP_COOLDOWN_SECONDS:
        del _recent_submissions[cache_key]
        return None

    existing_job = _jobs.get(entry["job_id"])
    if not existing_job:
        del _recent_submissions[cache_key]
        return None

    return existing_job


def _record_submission(job_type: str, dedup_key: str | None, job_id: str) -> None:
    """Record a job submission for deduplication tracking."""
    if not dedup_key:
        return
    cache_key = f"{job_type}:{dedup_key}"
    _recent_submissions[cache_key] = {
        "job_id": job_id,
        "submitted_at": datetime.now(timezone.utc),
    }


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


OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "http://openclaw:18789")
OPENCLAW_HOOKS_TOKEN = os.getenv("OPENCLAW_HOOKS_TOKEN", "")


async def _notify_via_openclaw(job: dict) -> None:
    """Push job result to the user via OpenClaw's webhook agent endpoint.

    OpenClaw receives the job payload, formats it using the
    deliver-job-result skill, and sends it to the user's chat channel.
    """
    if not OPENCLAW_HOOKS_TOKEN:
        logger.warning("OPENCLAW_HOOKS_TOKEN not set, skipping notification")
        return

    import json

    # Build a compact summary to avoid sending massive payloads
    compact_job = {
        "job_id": job.get("job_id"),
        "job_type": job.get("job_type"),
        "status": job.get("status"),
        "description": job.get("description"),
        "error": job.get("error"),
    }

    # For the result, only include what the agent needs to deliver
    result = job.get("result")
    if isinstance(result, dict):
        compact_result = {}
        for key in ("answer", "text", "file_path", "html_path", "data", "type",
                     "notebook_id", "title", "new_reports"):
            if key in result:
                value = result[key]
                # Truncate long text fields
                if isinstance(value, str) and len(value) > 3000:
                    compact_result[key] = value[:3000] + "... (truncated)"
                else:
                    compact_result[key] = value
        compact_job["result"] = compact_result
    elif result is not None:
        compact_job["result"] = str(result)[:3000]

    payload = {
        "message": (
            f"Deliver this job result to the user. "
            f"Job payload:\n```json\n{json.dumps(compact_job, default=str)}\n```"
        ),
        "name": f"job-result:{job.get('job_id', 'unknown')}",
        "sessionKey": "hook:jobs",
        "deliver": True,
        "channel": "all",
        "wakeMode": "now",
        "timeoutSeconds": 120,
    }

    url = f"{OPENCLAW_GATEWAY_URL}/hooks/agent"
    headers = {
        "Authorization": f"Bearer {OPENCLAW_HOOKS_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                logger.info("OpenClaw notified for job %s", job.get("job_id"))
            else:
                logger.error("OpenClaw webhook failed: %s %s", response.status_code, response.text[:200])
    except Exception as exc:
        logger.error("OpenClaw webhook error for job %s: %s", job.get("job_id"), exc)


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

    if job.get("notify"):
        logger.info("Job %s completed, sending notification via OpenClaw", job_id)
        try:
            await _notify_via_openclaw(job)
        except Exception as exc:
            logger.error("Notification failed for job %s: %s", job_id, exc)
            logger.error("Notification failed for job %s: %s", job_id, exc)


def submit_job(
    job_type: str,
    work_function,
    description: str = "",
    dedup_key: str | None = None,
    notify: bool = False,
) -> dict:
    """Submit a background job. Returns immediately with job_id.

    If dedup_key is provided, rejects duplicate submissions within the cooldown window.
    If notify is True, pushes the result to the user via OpenClaw webhook on completion.
    """
    existing = _check_dedup(job_type, dedup_key)
    if existing:
        return {
            **existing,
            "deduplicated": True,
            "message": f"Duplicate blocked. Same job submitted {DEDUP_COOLDOWN_SECONDS}s ago. "
            f"Use GET /api/jobs/{existing['job_id']} for results.",
        }

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
        "notify": notify,
    }

    _record_submission(job_type, dedup_key, job_id)
    asyncio.create_task(_run_job(job_id, work_function))

    return {
        "job_id": job_id,
        "status": "pending",
        "job_type": job_type,
        "description": description,
        "poll_url": f"/api/jobs/{job_id}",
        "message": f"Job started. Poll GET /api/jobs/{job_id} for results."
        + (" Notification will be sent on completion." if notify else ""),
    }


async def submit_and_wait(
    job_type: str,
    work_function,
    description: str = "",
    timeout: int = 300,
    dedup_key: str | None = None,
) -> dict:
    """Submit a job and block until it completes. Returns the full job result.

    This avoids the polling pattern entirely — one HTTP call, one result.
    Used by ?wait=true endpoints to save LLM context tokens.

    If dedup_key is provided, rejects duplicate submissions within the cooldown window.
    """
    existing = _check_dedup(job_type, dedup_key)
    if existing:
        return {
            **existing,
            "deduplicated": True,
            "message": f"Duplicate blocked. Same job submitted {DEDUP_COOLDOWN_SECONDS}s ago.",
        }

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

    _record_submission(job_type, dedup_key, job_id)
    task = asyncio.create_task(_run_job(job_id, work_function))

    try:
        await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = f"Job timed out after {timeout}s"
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

    return _jobs[job_id]


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
async def start_check_cycle(
    wait: bool = Query(False, description="Block until job completes"),
    timeout: int = Query(300, description="Max wait seconds (only with wait=true)"),
    notify: bool = Query(False, description="Push result to user via OpenClaw on completion"),
):
    """Start a full check cycle. Use wait=true to block until done."""
    async def do_work():
        from app.api.check_cycle import run_check_cycle
        session = _create_session()
        try:
            return run_check_cycle(session=session)
        finally:
            session.close()

    description = "Full check cycle: prices → portfolio → swing lows → rules"
    if wait:
        return await submit_and_wait("check-cycle", do_work, description, timeout)
    return submit_job("check-cycle", do_work, description, notify=notify)


@router.get("/start/fetch-reports")
async def start_fetch_reports(
    cafef_pages: int = Query(3, description="Number of CafeF pages to scrape (1-20)"),
    vietstock_pages: int = Query(3, description="Number of Vietstock pages to scrape (1-20)"),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Start scraping Vietstock + CafeF for new reports. Use wait=true to block."""
    async def do_work():
        from app.api.reports import fetch_reports
        session = _create_session()
        try:
            return await fetch_reports(
                cafef_pages=cafef_pages,
                vietstock_pages=vietstock_pages,
                session=session,
            )
        finally:
            session.close()

    description = f"Scraping Vietstock ({vietstock_pages}p) and CafeF ({cafef_pages}p) for reports"
    if wait:
        return await submit_and_wait("fetch-reports", do_work, description, timeout)
    return submit_job("fetch-reports", do_work, description, notify=notify)


@router.get("/start/fetch-prices")
async def start_fetch_prices(
    tickers: str = Query(
        ...,
        description="Comma-separated tickers (e.g. VCB,FPT,MBB)",
    ),
    days_back: int = Query(365),
    wait: bool = Query(False),
    timeout: int = Query(300),
    notify: bool = Query(False),
):
    """Start fetching prices for given tickers. Use wait=true to block."""
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

    description = f"Fetching prices for {', '.join(ticker_list)}"
    if wait:
        return await submit_and_wait("fetch-prices", do_work, description, timeout)
    return submit_job("fetch-prices", do_work, description, notify=notify)


@router.get("/start/evaluate-rules")
async def start_evaluate_rules(
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Start rules evaluation. Use wait=true to block."""
    async def do_work():
        from app.api.rules import evaluate
        session = _create_session()
        try:
            return evaluate(session=session)
        finally:
            session.close()

    description = "Evaluating trading rules"
    if wait:
        return await submit_and_wait("evaluate-rules", do_work, description, timeout)
    return submit_job("evaluate-rules", do_work, description, notify=notify)


@router.get("/start/execute-agent/{agent_id}")
async def start_execute_agent(
    agent_id: str,
    wait: bool = Query(False),
    timeout: int = Query(180),
    notify: bool = Query(False),
):
    """Start agent execution. Use wait=true to block."""
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

    description = f"Executing agent {agent_id}"
    if wait:
        return await submit_and_wait("execute-agent", do_work, description, timeout)
    return submit_job("execute-agent", do_work, description, notify=notify)


@router.get("/start/analyze")
async def start_analyze(
    edoc_id: str = Query(..., description="Report edoc_id"),
    question: str = Query(
        "Summarize this report in Vietnamese. Include key recommendations, target prices, and reasoning.",
        description="Question to ask about the report",
    ),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Start report analysis via NotebookLM as a background job.

    Routes the report to a persistent notebook by ticker or category,
    so context accumulates across multiple reports.
    """
    async def do_work():
        from app.api.analyze_report import (
            _download_report_pdf,
            _analyze_with_notebooklm,
        )
        from app.models import Report
        from app.notebooks import (
            resolve_notebook_target,
            get_or_create_notebook_mapping,
            save_notebook_mapping,
            increment_source_count,
        )

        session = _create_session()
        try:
            report = session.query(Report).filter_by(edoc_id=edoc_id).first()
            if not report:
                return {"error": f"Report {edoc_id} not found"}

            pdf_bytes = await _download_report_pdf(report.download_url)
            if not pdf_bytes:
                return {"error": f"Failed to download PDF from {report.download_url}"}

            # Route to the right notebook
            notebook_type, notebook_key, display_name = resolve_notebook_target(
                report.ticker, report.title,
            )
            existing = get_or_create_notebook_mapping(
                session, notebook_type, notebook_key, display_name,
            )
            existing_notebook_id = existing.notebook_id if existing else None

            result = await _analyze_with_notebooklm(
                pdf_bytes, report.title, question,
                existing_notebook_id=existing_notebook_id,
                notebook_display_name=display_name,
            )

            if result["created_new"]:
                save_notebook_mapping(
                    session, notebook_type, notebook_key,
                    result["notebook_id"], display_name,
                )
            elif existing:
                increment_source_count(session, existing)

            return {
                "edoc_id": edoc_id,
                "title": report.title,
                "notebook_id": result["notebook_id"],
                "notebook_type": notebook_type,
                "notebook_key": notebook_key,
                "answer": result["answer"],
            }
        finally:
            session.close()

    description = f"Analyzing report {edoc_id} via NotebookLM"
    dedup = edoc_id
    if wait:
        return await submit_and_wait("analyze", do_work, description, timeout, dedup_key=dedup)
    return submit_job("analyze", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/infographic")
async def start_infographic(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    language: str = Query("vi"),
    orientation: str = Query("portrait"),
    detail_level: str = Query("detailed"),
    instructions: str = Query(None),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Generate an infographic from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_infographic
        return await generate_infographic(notebook_id, language, orientation, detail_level, instructions)

    description = f"Generating infographic from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("infographic", do_work, description, timeout, dedup_key=dedup)
    return submit_job("infographic", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/audio")
async def start_audio(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    language: str = Query("vi"),
    audio_format: str = Query("deep_dive", description="deep_dive, brief, critique, debate"),
    audio_length: str = Query("default", description="short, default, long"),
    instructions: str = Query(None),
    wait: bool = Query(False),
    timeout: int = Query(180),
    notify: bool = Query(False),
):
    """Generate an audio overview from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_audio
        return await generate_audio(notebook_id, language, audio_format, audio_length, instructions)

    description = f"Generating {audio_format} audio from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("audio", do_work, description, timeout, dedup_key=dedup)
    return submit_job("audio", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/quiz")
async def start_quiz(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    quantity: str = Query("standard", description="fewer, standard"),
    difficulty: str = Query("medium", description="easy, medium, hard"),
    instructions: str = Query(None),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Generate a quiz with interactive HTML from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_quiz
        return await generate_quiz(notebook_id, quantity, difficulty, instructions)

    description = f"Generating quiz from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("quiz", do_work, description, timeout, dedup_key=dedup)
    return submit_job("quiz", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/flashcards")
async def start_flashcards(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    quantity: str = Query("standard", description="fewer, standard"),
    difficulty: str = Query("medium", description="easy, medium, hard"),
    instructions: str = Query(None),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Generate flashcards with interactive HTML from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_flashcards
        return await generate_flashcards(notebook_id, quantity, difficulty, instructions)

    description = f"Generating flashcards from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("flashcards", do_work, description, timeout, dedup_key=dedup)
    return submit_job("flashcards", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/slides")
async def start_slides(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    language: str = Query("vi"),
    slide_format: str = Query("detailed_deck", description="detailed_deck, presenter_slides"),
    slide_length: str = Query("default", description="default, short"),
    instructions: str = Query(None),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Generate a slide deck (PDF) from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_slide_deck
        return await generate_slide_deck(notebook_id, language, slide_format, slide_length, instructions)

    description = f"Generating slide deck from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("slides", do_work, description, timeout, dedup_key=dedup)
    return submit_job("slides", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/report")
async def start_report(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    language: str = Query("vi"),
    report_format: str = Query("briefing_doc", description="briefing_doc, study_guide, blog_post, custom"),
    custom_prompt: str = Query(None),
    instructions: str = Query(None),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Generate a report from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_report
        return await generate_report(notebook_id, language, report_format, custom_prompt)

    description = f"Generating {report_format} from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("report", do_work, description, timeout, dedup_key=dedup)
    return submit_job("report", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/video")
async def start_video(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    language: str = Query("vi"),
    video_format: str = Query("explainer", description="explainer, brief"),
    video_style: str = Query("auto_select", description="auto_select, classic, whiteboard, kawaii, anime, watercolor, retro_print, heritage, paper_craft"),
    instructions: str = Query(None),
    wait: bool = Query(False),
    timeout: int = Query(300),
    notify: bool = Query(False),
):
    """Generate a video from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_video
        return await generate_video(notebook_id, language, video_format, video_style, instructions)

    description = f"Generating {video_style} video from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("video", do_work, description, timeout, dedup_key=dedup)
    return submit_job("video", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/mind-map")
async def start_mind_map(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Generate a mind map from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_mind_map
        return await generate_mind_map(notebook_id)

    description = f"Generating mind map from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("mind_map", do_work, description, timeout, dedup_key=dedup)
    return submit_job("mind_map", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/study-guide")
async def start_study_guide(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    language: str = Query("vi"),
    instructions: str = Query(None),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Generate a study guide from a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import generate_study_guide
        return await generate_study_guide(notebook_id, language, instructions)

    description = f"Generating study guide from notebook {notebook_id[:8]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("study_guide", do_work, description, timeout, dedup_key=dedup)
    return submit_job("study_guide", do_work, description, dedup_key=dedup, notify=notify)


@router.get("/start/notebook-summary")
async def start_notebook_summary(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    wait: bool = Query(False),
    timeout: int = Query(60),
    notify: bool = Query(False),
):
    """Get a quick AI summary of a notebook. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import get_notebook_summary
        return await get_notebook_summary(notebook_id)

    description = f"Getting summary for notebook {notebook_id[:8]}"
    if wait:
        return await submit_and_wait("notebook_summary", do_work, description, timeout, dedup_key=notebook_id)
    return submit_job("notebook_summary", do_work, description, dedup_key=notebook_id, notify=notify)


@router.get("/start/chat")
async def start_chat(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    question: str = Query(..., description="Question to ask"),
    source_ids: str = Query(None, description="Comma-separated source IDs to filter"),
    wait: bool = Query(False),
    timeout: int = Query(60),
    notify: bool = Query(False),
):
    """Ask a follow-up question about a notebook. Use wait=true to block."""
    parsed_source_ids = (
        [s.strip() for s in source_ids.split(",") if s.strip()]
        if source_ids else None
    )

    async def do_work():
        from app.api.artifacts import chat_ask
        return await chat_ask(notebook_id, question, parsed_source_ids)

    description = f"Chat: {question[:50]}"
    if wait:
        return await submit_and_wait("chat", do_work, description, timeout)
    return submit_job("chat", do_work, description, notify=notify)


@router.get("/start/research")
async def start_research(
    notebook_id: str = Query(..., description="NotebookLM notebook ID"),
    query: str = Query(..., description="Research query"),
    source: str = Query("web", description="Research source: web"),
    mode: str = Query("fast", description="Research mode: fast"),
    wait: bool = Query(False),
    timeout: int = Query(120),
    notify: bool = Query(False),
):
    """Start web research from notebook context. Use wait=true to block."""
    async def do_work():
        from app.api.artifacts import start_research
        return await start_research(notebook_id, query, source, mode)

    description = f"Researching: {query[:50]}"
    dedup = notebook_id
    if wait:
        return await submit_and_wait("research", do_work, description, timeout, dedup_key=dedup)
    return submit_job("research", do_work, description, dedup_key=dedup, notify=notify)
