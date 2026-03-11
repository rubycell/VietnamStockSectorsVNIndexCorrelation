"""NotebookLM artifact generation API.

Generates infographics, audio overviews, quizzes, flashcards, slide decks,
reports, videos, mind maps, data tables, and study guides from notebooks.

All artifacts are generated asynchronously via the jobs system.
Quiz and flashcard artifacts are also rendered as interactive HTML files.
"""

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

NOTEBOOKLM_STORAGE = Path.home() / ".notebooklm" / "storage_state.json"
ARTIFACTS_DIR = Path("/tmp/notebooklm_artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)


def _check_login():
    if not NOTEBOOKLM_STORAGE.exists():
        raise HTTPException(status_code=503, detail="NotebookLM not logged in")


def _check_generation_status(status) -> None:
    """Raise a clear error if artifact generation failed (e.g. rate limit)."""
    if status.is_rate_limited:
        raise RuntimeError(
            "NotebookLM rate limit exceeded. Please wait 2-3 minutes before retrying."
        )
    if status.is_failed:
        raise RuntimeError(
            f"NotebookLM artifact generation failed: {status.error or 'unknown error'}"
        )
    if not status.task_id:
        raise RuntimeError(
            "NotebookLM returned empty task_id. The notebook may not have enough sources."
        )


# ---------------------------------------------------------------------------
# Infographic
# ---------------------------------------------------------------------------


async def generate_infographic(
    notebook_id: str,
    language: str = "vi",
    orientation: str = "portrait",
    detail_level: str = "detailed",
    instructions: str | None = None,
) -> dict:
    """Generate and download an infographic."""
    from notebooklm import NotebookLMClient
    from notebooklm.rpc.types import InfographicOrientation, InfographicDetail

    _check_login()

    orientation_map = {
        "landscape": InfographicOrientation.LANDSCAPE,
        "portrait": InfographicOrientation.PORTRAIT,
        "square": InfographicOrientation.SQUARE,
    }
    detail_map = {
        "concise": InfographicDetail.CONCISE,
        "standard": InfographicDetail.STANDARD,
        "detailed": InfographicDetail.DETAILED,
    }

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        status = await client.artifacts.generate_infographic(
            notebook_id=notebook_id,
            language=language,
            instructions=instructions,
            orientation=orientation_map.get(orientation.lower(), InfographicOrientation.PORTRAIT),
            detail_level=detail_map.get(detail_level.lower(), InfographicDetail.DETAILED),
        )
        _check_generation_status(status)
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)

        output_path = str(ARTIFACTS_DIR / f"infographic_{notebook_id[:8]}_{status.task_id[:8]}.png")
        saved = await client.artifacts.download_infographic(
            notebook_id, output_path, artifact_id=status.task_id,
        )
        return {"type": "infographic", "file_path": saved, "artifact_id": status.task_id}


# ---------------------------------------------------------------------------
# Audio Overview
# ---------------------------------------------------------------------------


async def generate_audio(
    notebook_id: str,
    language: str = "vi",
    audio_format: str = "deep_dive",
    audio_length: str = "default",
    instructions: str | None = None,
) -> dict:
    """Generate and download an audio overview."""
    from notebooklm import NotebookLMClient
    from notebooklm.rpc.types import AudioFormat, AudioLength

    _check_login()

    format_map = {
        "deep_dive": AudioFormat.DEEP_DIVE,
        "brief": AudioFormat.BRIEF,
        "critique": AudioFormat.CRITIQUE,
        "debate": AudioFormat.DEBATE,
    }
    length_map = {
        "short": AudioLength.SHORT,
        "default": AudioLength.DEFAULT,
        "long": AudioLength.LONG,
    }

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        status = await client.artifacts.generate_audio(
            notebook_id=notebook_id,
            language=language,
            instructions=instructions,
            audio_format=format_map.get(audio_format.lower(), AudioFormat.DEEP_DIVE),
            audio_length=length_map.get(audio_length.lower(), AudioLength.DEFAULT),
        )
        _check_generation_status(status)
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)

        output_path = str(ARTIFACTS_DIR / f"audio_{notebook_id[:8]}_{status.task_id[:8]}.mp3")
        saved = await client.artifacts.download_audio(
            notebook_id, output_path, artifact_id=status.task_id,
        )
        return {"type": "audio", "file_path": saved, "artifact_id": status.task_id}


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------


async def generate_quiz(
    notebook_id: str,
    quantity: str = "standard",
    difficulty: str = "medium",
    instructions: str | None = None,
) -> dict:
    """Generate a quiz, download as JSON, and render as interactive HTML."""
    from notebooklm import NotebookLMClient
    from notebooklm.rpc.types import QuizQuantity, QuizDifficulty

    _check_login()

    quantity_map = {"fewer": QuizQuantity.FEWER, "standard": QuizQuantity.STANDARD}
    difficulty_map = {
        "easy": QuizDifficulty.EASY,
        "medium": QuizDifficulty.MEDIUM,
        "hard": QuizDifficulty.HARD,
    }

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        status = await client.artifacts.generate_quiz(
            notebook_id=notebook_id,
            instructions=instructions,
            quantity=quantity_map.get(quantity.lower(), QuizQuantity.STANDARD),
            difficulty=difficulty_map.get(difficulty.lower(), QuizDifficulty.MEDIUM),
        )
        _check_generation_status(status)
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)

        json_path = str(ARTIFACTS_DIR / f"quiz_{notebook_id[:8]}_{status.task_id[:8]}.json")
        saved = await client.artifacts.download_quiz(
            notebook_id, json_path, artifact_id=status.task_id, output_format="json",
        )

        # Read JSON and render HTML
        quiz_data = json.loads(Path(saved).read_text())
        html_path = str(ARTIFACTS_DIR / f"quiz_{notebook_id[:8]}_{status.task_id[:8]}.html")
        Path(html_path).write_text(_render_quiz_html(quiz_data), encoding="utf-8")

        return {
            "type": "quiz",
            "json_path": saved,
            "html_path": html_path,
            "artifact_id": status.task_id,
            "question_count": len(quiz_data) if isinstance(quiz_data, list) else 0,
        }


# ---------------------------------------------------------------------------
# Flashcards
# ---------------------------------------------------------------------------


async def generate_flashcards(
    notebook_id: str,
    quantity: str = "standard",
    difficulty: str = "medium",
    instructions: str | None = None,
) -> dict:
    """Generate flashcards, download as JSON, and render as interactive HTML."""
    from notebooklm import NotebookLMClient
    from notebooklm.rpc.types import QuizQuantity, QuizDifficulty

    _check_login()

    quantity_map = {"fewer": QuizQuantity.FEWER, "standard": QuizQuantity.STANDARD}
    difficulty_map = {
        "easy": QuizDifficulty.EASY,
        "medium": QuizDifficulty.MEDIUM,
        "hard": QuizDifficulty.HARD,
    }

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        status = await client.artifacts.generate_flashcards(
            notebook_id=notebook_id,
            instructions=instructions,
            quantity=quantity_map.get(quantity.lower(), QuizQuantity.STANDARD),
            difficulty=difficulty_map.get(difficulty.lower(), QuizDifficulty.MEDIUM),
        )
        _check_generation_status(status)
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)

        json_path = str(ARTIFACTS_DIR / f"flashcards_{notebook_id[:8]}_{status.task_id[:8]}.json")
        saved = await client.artifacts.download_flashcards(
            notebook_id, json_path, artifact_id=status.task_id, output_format="json",
        )

        cards_data = json.loads(Path(saved).read_text())
        html_path = str(ARTIFACTS_DIR / f"flashcards_{notebook_id[:8]}_{status.task_id[:8]}.html")
        Path(html_path).write_text(_render_flashcards_html(cards_data), encoding="utf-8")

        return {
            "type": "flashcards",
            "json_path": saved,
            "html_path": html_path,
            "artifact_id": status.task_id,
            "card_count": len(cards_data) if isinstance(cards_data, list) else 0,
        }


# ---------------------------------------------------------------------------
# Slide Deck
# ---------------------------------------------------------------------------


async def generate_slide_deck(
    notebook_id: str,
    language: str = "vi",
    slide_format: str = "detailed_deck",
    slide_length: str = "default",
    instructions: str | None = None,
) -> dict:
    """Generate and download a slide deck as PDF."""
    from notebooklm import NotebookLMClient
    from notebooklm.rpc.types import SlideDeckFormat, SlideDeckLength

    _check_login()

    format_map = {
        "detailed_deck": SlideDeckFormat.DETAILED_DECK,
        "presenter_slides": SlideDeckFormat.PRESENTER_SLIDES,
    }
    length_map = {
        "default": SlideDeckLength.DEFAULT,
        "short": SlideDeckLength.SHORT,
    }

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        status = await client.artifacts.generate_slide_deck(
            notebook_id=notebook_id,
            language=language,
            instructions=instructions,
            slide_format=format_map.get(slide_format.lower(), SlideDeckFormat.DETAILED_DECK),
            slide_length=length_map.get(slide_length.lower(), SlideDeckLength.DEFAULT),
        )
        _check_generation_status(status)
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)

        output_path = str(ARTIFACTS_DIR / f"slides_{notebook_id[:8]}_{status.task_id[:8]}.pdf")
        saved = await client.artifacts.download_slide_deck(
            notebook_id, output_path, artifact_id=status.task_id, output_format="pdf",
        )
        return {"type": "slide_deck", "file_path": saved, "artifact_id": status.task_id}


# ---------------------------------------------------------------------------
# Report (Briefing Doc / Blog Post / Study Guide / Custom)
# ---------------------------------------------------------------------------


async def generate_report(
    notebook_id: str,
    language: str = "vi",
    report_format: str = "briefing_doc",
    custom_prompt: str | None = None,
) -> dict:
    """Generate and download a report."""
    from notebooklm import NotebookLMClient
    from notebooklm.rpc.types import ReportFormat

    _check_login()

    format_map = {
        "briefing_doc": ReportFormat.BRIEFING_DOC,
        "study_guide": ReportFormat.STUDY_GUIDE,
        "blog_post": ReportFormat.BLOG_POST,
        "custom": ReportFormat.CUSTOM,
    }

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        status = await client.artifacts.generate_report(
            notebook_id=notebook_id,
            language=language,
            report_format=format_map.get(report_format.lower(), ReportFormat.BRIEFING_DOC),
            custom_prompt=custom_prompt,
        )
        _check_generation_status(status)
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)

        output_path = str(ARTIFACTS_DIR / f"report_{notebook_id[:8]}_{status.task_id[:8]}.md")
        saved = await client.artifacts.download_report(
            notebook_id, output_path, artifact_id=status.task_id,
        )

        report_text = Path(saved).read_text(encoding="utf-8")
        return {
            "type": "report",
            "file_path": saved,
            "artifact_id": status.task_id,
            "text": report_text[:5000],
        }


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------


async def generate_video(
    notebook_id: str,
    language: str = "vi",
    video_format: str = "explainer",
    video_style: str = "auto_select",
    instructions: str | None = None,
) -> dict:
    """Generate and download a video."""
    from notebooklm import NotebookLMClient
    from notebooklm.rpc.types import VideoFormat, VideoStyle

    _check_login()

    format_map = {
        "explainer": VideoFormat.EXPLAINER,
        "brief": VideoFormat.BRIEF,
    }
    style_map = {
        "auto_select": VideoStyle.AUTO_SELECT,
        "classic": VideoStyle.CLASSIC,
        "whiteboard": VideoStyle.WHITEBOARD,
        "kawaii": VideoStyle.KAWAII,
        "anime": VideoStyle.ANIME,
        "watercolor": VideoStyle.WATERCOLOR,
        "retro_print": VideoStyle.RETRO_PRINT,
        "heritage": VideoStyle.HERITAGE,
        "paper_craft": VideoStyle.PAPER_CRAFT,
    }

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        status = await client.artifacts.generate_video(
            notebook_id=notebook_id,
            language=language,
            instructions=instructions,
            video_format=format_map.get(video_format.lower(), VideoFormat.EXPLAINER),
            video_style=style_map.get(video_style.lower(), VideoStyle.AUTO_SELECT),
        )
        _check_generation_status(status)
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)

        output_path = str(ARTIFACTS_DIR / f"video_{notebook_id[:8]}_{status.task_id[:8]}.mp4")
        saved = await client.artifacts.download_video(
            notebook_id, output_path, artifact_id=status.task_id,
        )
        return {"type": "video", "file_path": saved, "artifact_id": status.task_id}


# ---------------------------------------------------------------------------
# Mind Map
# ---------------------------------------------------------------------------


async def generate_mind_map(notebook_id: str) -> dict:
    """Generate a mind map (returns JSON structure)."""
    from notebooklm import NotebookLMClient

    _check_login()

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        result = await client.artifacts.generate_mind_map(notebook_id)

        json_path = str(ARTIFACTS_DIR / f"mindmap_{notebook_id[:8]}.json")
        Path(json_path).write_text(json.dumps(result, ensure_ascii=False, indent=2))

        return {"type": "mind_map", "json_path": json_path, "data": result}


# ---------------------------------------------------------------------------
# Study Guide
# ---------------------------------------------------------------------------


async def generate_study_guide(
    notebook_id: str,
    language: str = "vi",
    instructions: str | None = None,
) -> dict:
    """Generate a study guide."""
    from notebooklm import NotebookLMClient

    _check_login()

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        status = await client.artifacts.generate_study_guide(
            notebook_id=notebook_id,
            language=language,
            extra_instructions=instructions,
        )
        _check_generation_status(status)
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)

        # Study guide is typically text — download as report
        output_path = str(ARTIFACTS_DIR / f"study_guide_{notebook_id[:8]}_{status.task_id[:8]}.md")
        saved = await client.artifacts.download_report(
            notebook_id, output_path, artifact_id=status.task_id,
        )

        text = Path(saved).read_text(encoding="utf-8")
        return {
            "type": "study_guide",
            "file_path": saved,
            "artifact_id": status.task_id,
            "text": text[:5000],
        }


# ---------------------------------------------------------------------------
# Notebook Summary (quick, no artifact generation)
# ---------------------------------------------------------------------------


async def get_notebook_summary(notebook_id: str) -> dict:
    """Get a quick AI summary of a notebook without generating artifacts."""
    from notebooklm import NotebookLMClient

    _check_login()

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        summary = await client.notebooks.get_summary(notebook_id)
        return {"type": "summary", "notebook_id": notebook_id, "text": summary}


# ---------------------------------------------------------------------------
# Chat (ask follow-up questions, optionally filtered by source)
# ---------------------------------------------------------------------------


async def chat_ask(
    notebook_id: str,
    question: str,
    source_ids: list[str] | None = None,
) -> dict:
    """Ask a follow-up question about a notebook, optionally filtered to specific sources."""
    from notebooklm import NotebookLMClient

    _check_login()

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        result = await client.chat.ask(
            notebook_id=notebook_id,
            question=question,
            source_ids=source_ids,
        )
        return {
            "type": "chat",
            "notebook_id": notebook_id,
            "question": question,
            "answer": result.answer,
            "source_ids": source_ids,
        }


# ---------------------------------------------------------------------------
# Research (web research from notebook context)
# ---------------------------------------------------------------------------


async def start_research(
    notebook_id: str,
    query: str,
    source: str = "web",
    mode: str = "fast",
) -> dict:
    """Start a web research task from notebook context."""
    from notebooklm import NotebookLMClient

    _check_login()

    async with await NotebookLMClient.from_storage(
        path=str(NOTEBOOKLM_STORAGE),
    ) as client:
        result = await client.research.start(
            notebook_id=notebook_id,
            query=query,
            source=source,
            mode=mode,
        )
        if result is None:
            return {"type": "research", "status": "failed", "error": "Research returned no results"}

        # Poll until done
        import asyncio
        for _ in range(30):
            poll = await client.research.poll(notebook_id)
            status = poll.get("status", "")
            if status in ("completed", "done", "finished"):
                return {
                    "type": "research",
                    "status": "completed",
                    "notebook_id": notebook_id,
                    "query": query,
                    "data": poll,
                }
            if status in ("failed", "error"):
                return {"type": "research", "status": "failed", "error": str(poll)}
            await asyncio.sleep(2)

        return {"type": "research", "status": "timeout", "data": poll}


# ---------------------------------------------------------------------------
# File download endpoint
# ---------------------------------------------------------------------------


@router.get("/download")
async def download_artifact(file_path: str = Query(...)):
    """Download a generated artifact file."""
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not str(path).startswith(str(ARTIFACTS_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(path, filename=path.name)


# ---------------------------------------------------------------------------
# HTML Renderers
# ---------------------------------------------------------------------------


def _render_quiz_html(quiz_data: list | dict) -> str:
    """Render quiz JSON as an interactive HTML page."""
    questions = quiz_data if isinstance(quiz_data, list) else quiz_data.get("questions", [])
    questions_json = json.dumps(questions, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Quiz - NotebookLM</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0f172a; color: #e2e8f0; padding: 20px; max-width: 720px; margin: 0 auto; }}
h1 {{ text-align: center; margin: 20px 0 30px; color: #38bdf8; font-size: 1.5em; }}
.score {{ text-align: center; font-size: 1.2em; margin-bottom: 24px; color: #94a3b8; }}
.score span {{ color: #22d3ee; font-weight: bold; }}
.question {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 16px;
             border: 1px solid #334155; transition: border-color 0.3s; }}
.question.correct {{ border-color: #22c55e; }}
.question.wrong {{ border-color: #ef4444; }}
.q-text {{ font-size: 1.05em; margin-bottom: 14px; line-height: 1.5; }}
.q-num {{ color: #38bdf8; font-weight: bold; }}
.options {{ display: flex; flex-direction: column; gap: 8px; }}
.option {{ background: #334155; border: 2px solid transparent; border-radius: 8px; padding: 12px 16px;
          cursor: pointer; transition: all 0.2s; font-size: 0.95em; }}
.option:hover:not(.disabled) {{ background: #475569; border-color: #64748b; }}
.option.selected {{ border-color: #38bdf8; background: #1e3a5f; }}
.option.correct-answer {{ border-color: #22c55e; background: #14532d; }}
.option.wrong-answer {{ border-color: #ef4444; background: #450a0a; }}
.option.disabled {{ cursor: default; opacity: 0.7; }}
.explanation {{ margin-top: 12px; padding: 12px; background: #0f172a; border-radius: 8px;
               border-left: 3px solid #38bdf8; display: none; font-size: 0.9em; line-height: 1.4; }}
.explanation.show {{ display: block; }}
.btn {{ display: block; margin: 24px auto; padding: 14px 32px; background: #2563eb; color: white;
        border: none; border-radius: 8px; font-size: 1em; cursor: pointer; }}
.btn:hover {{ background: #1d4ed8; }}
</style>
</head>
<body>
<h1>Quiz</h1>
<div class="score">Score: <span id="score">0</span> / <span id="total">0</span></div>
<div id="questions"></div>
<button class="btn" id="resetBtn" style="display:none" onclick="resetQuiz()">Làm lại</button>
<script>
const questions = {questions_json};
let answered = 0, correct = 0;
const container = document.getElementById('questions');
const totalEl = document.getElementById('total');
const scoreEl = document.getElementById('score');
totalEl.textContent = questions.length;

questions.forEach((q, qi) => {{
  const div = document.createElement('div');
  div.className = 'question';
  div.id = 'q' + qi;

  const qText = q.question || q.text || q.prompt || '';
  const options = q.options || q.choices || q.answers || [];
  const correctIdx = typeof q.correct_answer === 'number' ? q.correct_answer
    : typeof q.answer === 'number' ? q.answer
    : typeof q.correct === 'number' ? q.correct
    : options.findIndex(o => o === q.correct_answer || o === q.answer);
  const explanation = q.explanation || q.rationale || '';

  let html = '<div class="q-text"><span class="q-num">Q' + (qi+1) + '.</span> ' + qText + '</div>';
  html += '<div class="options">';
  options.forEach((opt, oi) => {{
    const optText = typeof opt === 'string' ? opt : opt.text || opt.label || String(opt);
    html += '<div class="option" data-q="' + qi + '" data-o="' + oi + '" data-correct="' + correctIdx + '" onclick="selectOption(this)">' + optText + '</div>';
  }});
  html += '</div>';
  html += '<div class="explanation" id="exp' + qi + '">' + explanation + '</div>';
  div.innerHTML = html;
  container.appendChild(div);
}});

function selectOption(el) {{
  if (el.classList.contains('disabled')) return;
  const qi = parseInt(el.dataset.q);
  const oi = parseInt(el.dataset.o);
  const ci = parseInt(el.dataset.correct);
  const qDiv = document.getElementById('q' + qi);
  const allOpts = qDiv.querySelectorAll('.option');

  allOpts.forEach(o => {{ o.classList.add('disabled'); }});
  if (oi === ci) {{
    el.classList.add('correct-answer');
    qDiv.classList.add('correct');
    correct++;
  }} else {{
    el.classList.add('wrong-answer');
    allOpts[ci]?.classList.add('correct-answer');
    qDiv.classList.add('wrong');
  }}
  answered++;
  scoreEl.textContent = correct;
  document.getElementById('exp' + qi).classList.add('show');
  if (answered === questions.length) document.getElementById('resetBtn').style.display = 'block';
}}

function resetQuiz() {{
  answered = 0; correct = 0; scoreEl.textContent = 0;
  document.querySelectorAll('.question').forEach(q => {{
    q.classList.remove('correct', 'wrong');
    q.querySelectorAll('.option').forEach(o => {{
      o.classList.remove('disabled', 'correct-answer', 'wrong-answer', 'selected');
    }});
  }});
  document.querySelectorAll('.explanation').forEach(e => e.classList.remove('show'));
  document.getElementById('resetBtn').style.display = 'none';
}}
</script>
</body>
</html>"""


def _render_flashcards_html(cards_data: list | dict) -> str:
    """Render flashcards JSON as an interactive flip-card HTML page."""
    cards = cards_data if isinstance(cards_data, list) else cards_data.get("cards", [])
    cards_json = json.dumps(cards, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flashcards - NotebookLM</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0f172a; color: #e2e8f0; display: flex; flex-direction: column;
       align-items: center; padding: 20px; min-height: 100vh; }}
h1 {{ color: #38bdf8; margin: 20px 0; font-size: 1.5em; }}
.counter {{ color: #94a3b8; margin-bottom: 24px; font-size: 1.1em; }}
.counter span {{ color: #22d3ee; font-weight: bold; }}
.card-container {{ perspective: 1000px; width: 100%; max-width: 500px; height: 300px;
                   margin-bottom: 24px; cursor: pointer; }}
.card {{ width: 100%; height: 100%; position: relative; transition: transform 0.6s;
        transform-style: preserve-3d; }}
.card.flipped {{ transform: rotateY(180deg); }}
.card-face {{ position: absolute; width: 100%; height: 100%; backface-visibility: hidden;
             border-radius: 16px; display: flex; align-items: center; justify-content: center;
             padding: 24px; text-align: center; font-size: 1.1em; line-height: 1.6; }}
.card-front {{ background: linear-gradient(135deg, #1e3a5f, #1e293b); border: 2px solid #334155; }}
.card-back {{ background: linear-gradient(135deg, #14532d, #1e293b); border: 2px solid #22c55e;
             transform: rotateY(180deg); }}
.hint {{ color: #64748b; font-size: 0.85em; margin-top: 8px; }}
.nav {{ display: flex; gap: 16px; }}
.nav button {{ padding: 12px 28px; border-radius: 8px; border: none; font-size: 1em;
              cursor: pointer; transition: background 0.2s; }}
.prev {{ background: #334155; color: #e2e8f0; }}
.prev:hover {{ background: #475569; }}
.next {{ background: #2563eb; color: white; }}
.next:hover {{ background: #1d4ed8; }}
.flip-hint {{ color: #64748b; font-size: 0.85em; margin-bottom: 12px; }}
.progress {{ width: 100%; max-width: 500px; height: 4px; background: #334155;
            border-radius: 2px; margin-bottom: 16px; overflow: hidden; }}
.progress-bar {{ height: 100%; background: #38bdf8; transition: width 0.3s; }}
</style>
</head>
<body>
<h1>Flashcards</h1>
<div class="counter">Card <span id="current">1</span> / <span id="total">0</span></div>
<div class="progress"><div class="progress-bar" id="progressBar"></div></div>
<p class="flip-hint">Tap card to flip</p>
<div class="card-container" onclick="flipCard()">
  <div class="card" id="card">
    <div class="card-face card-front" id="front"></div>
    <div class="card-face card-back" id="back"></div>
  </div>
</div>
<div class="nav">
  <button class="prev" onclick="prevCard()">Previous</button>
  <button class="next" onclick="nextCard()">Next</button>
</div>
<script>
const cards = {cards_json};
let idx = 0;
const totalEl = document.getElementById('total');
const currentEl = document.getElementById('current');
const frontEl = document.getElementById('front');
const backEl = document.getElementById('back');
const cardEl = document.getElementById('card');
const progressBar = document.getElementById('progressBar');
totalEl.textContent = cards.length;

function showCard() {{
  const c = cards[idx];
  const front = c.front || c.question || c.term || c.concept || '';
  const back = c.back || c.answer || c.definition || c.explanation || '';
  frontEl.innerHTML = front;
  backEl.innerHTML = back;
  currentEl.textContent = idx + 1;
  cardEl.classList.remove('flipped');
  progressBar.style.width = ((idx + 1) / cards.length * 100) + '%';
}}

function flipCard() {{ cardEl.classList.toggle('flipped'); }}
function nextCard() {{ if (idx < cards.length - 1) {{ idx++; showCard(); }} }}
function prevCard() {{ if (idx > 0) {{ idx--; showCard(); }} }}

document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight') nextCard();
  else if (e.key === 'ArrowLeft') prevCard();
  else if (e.key === ' ') {{ e.preventDefault(); flipCard(); }}
}});

showCard();
</script>
</body>
</html>"""
