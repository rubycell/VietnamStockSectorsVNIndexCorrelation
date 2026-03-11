"""Analyze Vietstock reports using Google NotebookLM."""

import asyncio
import tempfile
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


class AnalyzeRequest(BaseModel):
    edoc_id: str
    question: str = "Summarize this report in Vietnamese. Include key recommendations, target prices, and reasoning."


class AnalyzeResponse(BaseModel):
    edoc_id: str
    title: str
    notebook_id: str
    answer: str
    error: str | None = None


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
) -> dict:
    """Create a NotebookLM notebook, add PDF source, and ask a question."""
    from notebooklm import NotebookLMClient

    storage_path = str(NOTEBOOKLM_STORAGE)
    if not NOTEBOOKLM_STORAGE.exists():
        raise FileNotFoundError(
            "NotebookLM credentials not found. Run 'notebooklm login' first."
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_file.write(pdf_bytes)
        temp_path = temp_file.name

    try:
        async with await NotebookLMClient.from_storage(path=storage_path) as client:
            notebook = await client.notebooks.create(f"Report: {title[:80]}")
            notebook_id = notebook.id

            await client.sources.add_file(
                notebook_id, temp_path, wait=True
            )

            result = await client.chat.ask(notebook_id, question)

            return {
                "notebook_id": notebook_id,
                "answer": result.answer,
            }
    finally:
        Path(temp_path).unlink(missing_ok=True)


@router.post("", response_model=AnalyzeResponse)
async def analyze_report(
    request: AnalyzeRequest,
    session: Session = Depends(get_database_session),
):
    """Analyze a report by edoc_id using NotebookLM."""
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


@router.get("/notebooks")
async def list_notebooks():
    """List all NotebookLM notebooks (for management)."""
    from notebooklm import NotebookLMClient

    if not NOTEBOOKLM_STORAGE.exists():
        raise HTTPException(status_code=503, detail="NotebookLM not logged in")

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE)
    ) as client:
        notebooks = await client.notebooks.list()
        return {
            "notebooks": [
                {"id": nb.id, "title": nb.title}
                for nb in notebooks
            ],
            "count": len(notebooks),
        }
