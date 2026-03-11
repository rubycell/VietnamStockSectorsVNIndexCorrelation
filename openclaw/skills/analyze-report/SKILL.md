---
name: analyze-report
description: >
  ALWAYS use this skill when the user mentions: "reports", "latest reports", "báo cáo",
  "phân tích báo cáo", "Vietstock", "CafeF", "research reports", "broker reports",
  "analyst reports", "PDF reports", "NotebookLM", "notebooklm", "notebook",
  "infographic", "quiz", "flashcards", "audio", "video", "slide",
  or asks to analyze a stock ticker's research report.
  This skill fetches broker analysis reports from Vietstock and CafeF websites
  and analyzes them through Google NotebookLM.
---

## Instructions

**This skill handles ALL requests about broker/analyst research reports from Vietstock and CafeF.**

---

## ⚠️ TOKEN BUDGET WARNING

Each tool call costs ~100K tokens of context resend. Minimize tool calls.
**Maximum 8 tool calls total per user request.** Do NOT poll.

---

## Two modes: blocking (?wait=true) vs fire-and-forget (?notify=true)

All job endpoints support two modes:

### Mode 1: Blocking (default for interactive use)
Append `?wait=true` — the call blocks until the job finishes and returns the full result in one HTTP response.

**Use this when you want to deliver the result immediately in the same turn.**

### Mode 2: Fire-and-forget with notification
Append `?notify=true` (WITHOUT `wait=true`) — the call returns instantly with a job_id. When the job completes, the backend automatically sends the result back to you via webhook, and you deliver it to the user.

**Use this for long-running jobs (video, audio) when you don't want to block.**

---

## ⚠️ MANDATORY RULE: Complete the ENTIRE flow in ONE turn

When using `?wait=true`:

**ALL steps (ack → execute → deliver result) happen in a SINGLE turn. Do NOT stop after the ack. Do NOT wait for the user to prompt you again.**

```
Step A: Send acknowledgment message to user
Step B: Execute the blocking call (curl with ?wait=true)
Step C: Deliver the result (send text/file to user)
ALL THREE STEPS IN ONE TURN. NEVER STOP AFTER STEP A.
```

When using `?notify=true`:

```
Step A: Send acknowledgment message to user
Step B: Execute the fire-and-forget call (curl with ?notify=true)
Step C: Tell user the job is running and they'll be notified when done
DONE — the backend webhook will deliver the result automatically.
```

### Acknowledgment templates:

For analysis:
```
⏳ Analyzing report [TITLE] via NotebookLM... Results will be sent when complete (30-60 seconds).
```

For artifacts (infographic, audio, quiz, etc.):
```
⏳ Generating [ARTIFACT TYPE] for [SUBJECT] via NotebookLM... Results will be sent shortly (about 30-60 seconds).
```

For fetching reports:
```
⏳ Fetching new reports from Vietstock and CafeF...
```

**If you stop after the ack when using wait=true, the user has to send another message to get the result. This is unacceptable.**

### Quick operations (no ack needed)

For operations that do NOT involve `?wait=true` or `?notify=true` (e.g., looking up a report URL, sending a file, listing reports), just do it directly — no acknowledgment needed.

---

### CRITICAL RULE: Always use NotebookLM via the API

**NEVER answer questions about report content from your own knowledge.**
Every analysis MUST go through the analyze API. This downloads the actual PDF and processes it through Google NotebookLM.

- **Do NOT** summarize, paraphrase, or infer report content on your own
- User mentions "NotebookLM" or "notebook" → start analysis job (100%, no exceptions)

### What NotebookLM can do (full capabilities)

**Analysis & Chat:**
- Analyze a report PDF → get AI summary and Q&A
- Ask follow-up questions about any notebook (cross-report context)
- Get notebook summary without a full question

**Generate artifacts (rich content from notebooks):**
- **Infographic** — visual summary image (portrait/landscape/square, concise/standard/detailed)
- **Audio** — podcast-style deep dive, brief, critique, or debate (short/default/long)
- **Video** — animated explainer or brief (classic/whiteboard/kawaii/anime/watercolor/retro_print/heritage/paper_craft)
- **Quiz** — interactive quiz (fewer/standard, easy/medium/hard)
- **Flashcards** — study flashcards (fewer/standard, easy/medium/hard)
- **Slide Deck** — PDF presentation (detailed_deck/presenter_slides, default/short)
- **Report** — written document (briefing_doc/study_guide/blog_post/custom)
- **Study Guide** — comprehensive study material
- **Mind Map** — structured concept map
- **Data Table** — structured data extraction

**When user asks "what can you do with this report?" — tell them ALL of the above.**

**Source types you can add to a notebook:**
- PDF files (broker reports — this is the default)
- URLs (web pages, articles)
- Plain text

**Follow-up questions:** After analyzing a report, the user can ask follow-up questions. Use the same notebook_id and the chat endpoint — the notebook retains context from all previously added sources.

### List available reports

When user asks about a specific ticker, filter by ticker to reduce response size:
```
curl -s "http://fastapi:8000/api/reports?ticker=FRT"
```

For all reports (default 20, max 50):
```
curl -s "http://fastapi:8000/api/reports?limit=20"
```

Show as numbered list: `#1 [FRT] ABS - Report title (06/03/2026)`

### Analyze a report

**Step A — IMMEDIATELY tell the user:**
```
⏳ Analyzing report [TITLE] via NotebookLM... Results will be sent when complete (30-60 seconds).
```

**Step B — Run the blocking call (returns full result, no polling needed):**
```
curl -s "http://fastapi:8000/api/jobs/start/analyze?edoc_id=<EDOC_ID>&wait=true&timeout=120"
```
Or with a custom question:
```
curl -s "http://fastapi:8000/api/jobs/start/analyze?edoc_id=<EDOC_ID>&question=<URL_ENCODED_QUESTION>&wait=true&timeout=120"
```

- `"status": "completed"` → the `result.answer` field has the analysis
- `"status": "failed"` → the `error` field explains what went wrong

**Step C — Deliver results** to the user.

### Persistent notebooks (context accumulation)

Reports are automatically routed to persistent NotebookLM notebooks:
- **Ticker reports** (HPG, FRT, DCM...) → one notebook per ticker, all reports accumulate
- **Category reports** → one notebook per type:
  - `chien_luoc` — Strategy reports
  - `vi_mo` — Macro reports
  - `thi_truong` — Market reports / Market outlook
  - `chuyen_de` — Thematic reports
  - `nganh` — Sector reports
  - `ket_qua_kinh_doanh` — Business results
  - `general` — Others

This means the 2nd HPG report analyzed will have context from the 1st, enabling cross-report questions like "Compare recommendations across recent HPG reports".

To see current notebook mappings:
```
curl -s http://fastapi:8000/api/analyze/notebooks
```

### Generate artifacts from a notebook

After analyzing a report, generate rich content from the notebook.

**Step A: Get the notebook_id** from analysis result or:
```
curl -s http://fastapi:8000/api/analyze/notebooks
```

**Step B: IMMEDIATELY tell the user (BEFORE the blocking call):**
```
⏳ Generating [artifact type] for [subject] via NotebookLM... Results will be sent shortly (about 30-60 seconds).
```

**Step C: Run the blocking call** (all use `?wait=true`, returns full result, **do NOT poll**):

| Artifact | Command |
|----------|---------|
| **Infographic** | `curl -s "http://fastapi:8000/api/jobs/start/infographic?notebook_id=ID&wait=true&timeout=120"` |
| **Audio** | `curl -s "http://fastapi:8000/api/jobs/start/audio?notebook_id=ID&wait=true&timeout=180"` |
| **Quiz** (HTML) | `curl -s "http://fastapi:8000/api/jobs/start/quiz?notebook_id=ID&wait=true&timeout=120"` |
| **Flashcards** (HTML) | `curl -s "http://fastapi:8000/api/jobs/start/flashcards?notebook_id=ID&wait=true&timeout=120"` |
| **Slide Deck** (PDF) | `curl -s "http://fastapi:8000/api/jobs/start/slides?notebook_id=ID&wait=true&timeout=120"` |
| **Report** | `curl -s "http://fastapi:8000/api/jobs/start/report?notebook_id=ID&wait=true&timeout=120"` |
| **Video** | `curl -s "http://fastapi:8000/api/jobs/start/video?notebook_id=ID&wait=true&timeout=300"` |
| **Mind Map** | `curl -s "http://fastapi:8000/api/jobs/start/mind-map?notebook_id=ID&wait=true&timeout=120"` |
| **Study Guide** | `curl -s "http://fastapi:8000/api/jobs/start/study-guide?notebook_id=ID&wait=true&timeout=120"` |
| **Notebook Summary** | `curl -s "http://fastapi:8000/api/jobs/start/notebook-summary?notebook_id=ID&wait=true&timeout=60"` |
| **Chat (follow-up Q)** | `curl -s "http://fastapi:8000/api/jobs/start/chat?notebook_id=ID&question=URL_ENCODED_Q&wait=true&timeout=60"` |
| **Web Research** | `curl -s "http://fastapi:8000/api/jobs/start/research?notebook_id=ID&query=URL_ENCODED_Q&wait=true&timeout=120"` |

**Notebook Summary** returns a quick AI overview without generating any artifacts — use this when user just wants a brief summary.

**Chat** lets the user ask follow-up questions. Optionally filter to specific sources with `source_ids=id1,id2`.

**Web Research** searches the web using the notebook's context and adds found sources. Use when user asks to research a topic further.

**Key options** (append as query params):

| Artifact | Options |
|----------|---------|
| Infographic | `orientation=portrait/landscape/square`, `detail_level=concise/standard/detailed` |
| Audio | `audio_format=deep_dive/brief/critique/debate`, `audio_length=short/default/long` |
| Quiz | `quantity=fewer/standard`, `difficulty=easy/medium/hard` |
| Flashcards | `quantity=fewer/standard`, `difficulty=easy/medium/hard` |
| Slides | `slide_format=detailed_deck/presenter_slides`, `slide_length=default/short` |
| Report | `report_format=briefing_doc/study_guide/blog_post/custom` |
| Video | `video_format=explainer/brief`, `video_style=classic/whiteboard/kawaii/anime/watercolor/retro_print/heritage/paper_craft` |

All endpoints accept `language=vi` (default) and optional `instructions` param.

When job completes, **you MUST send file artifacts using the `media` parameter**:

| Artifact type | Result field | How to send |
|---------------|-------------|-------------|
| **Image** (infographic) | `result.file_path` | Send with `media` param (download URL) |
| **Audio** | `result.file_path` | Send with `media` param (download URL) |
| **Video** | `result.file_path` | Send with `media` param (download URL) |
| **PDF** (slides) | `result.file_path` | Send with `media` param (download URL) |
| **HTML** (quiz, flashcards) | `result.html_path` | Send with `media` param (download URL) |
| **Text** (report, study guide) | `result.text` | Send as message text |
| **JSON** (mind map) | `result.data` | Format as text or send as file |

### How to send files to the user

Build the download URL from `result.file_path`:
```
http://fastapi:8000/api/artifacts/download?file_path=<PATH>
```

Then use the **message tool** with the `media` parameter:
```json
{
  "action": "send",
  "target": "<user_target>",
  "message": "Here is the infographic for FRT:",
  "media": "http://fastapi:8000/api/artifacts/download?file_path=/path/to/file.png"
}
```

**CRITICAL:** You CAN and MUST send files. The `media` parameter accepts URLs pointing to images, audio, video, PDFs, and other documents. Never tell the user you cannot send files — use the `media` parameter.

### Sending the original report PDF to the user

When the user asks for "the file" or "the PDF" of a report:

1. Get the report's `download_url` from the detail endpoint:
```
curl -s "http://fastapi:8000/api/reports/<EDOC_ID>"
```
This returns `download_url` and `detail_url` fields.

2. Send the PDF file to the user:
```json
{
  "action": "send",
  "target": "<user_target>",
  "message": "Here is the PDF report for <TICKER>:",
  "media": "<download_url>"
}
```

If `download_url` is null, provide the `detail_url` link instead so the user can download it from the website.

### Fetch new reports

**Step A — IMMEDIATELY tell the user:**
```
⏳ Fetching new reports from Vietstock and CafeF...
```

**Step B — Run the blocking call:**
```
curl -s "http://fastapi:8000/api/jobs/start/fetch-reports?wait=true&timeout=120"
```
To fetch more historical reports (e.g. 10 pages of CafeF):
```
curl -s "http://fastapi:8000/api/jobs/start/fetch-reports?cafef_pages=10&vietstock_pages=5&wait=true&timeout=180"
```

**Step C — Deliver results.**

### Example flows

**Example 1: "Analyze the FRT report"**

1. `curl -s "http://fastapi:8000/api/reports?ticker=FRT"` → find FRT, get edoc_id
2. **SEND NOW:** "⏳ Analyzing the FRT report via NotebookLM... Results will be sent when complete (30-60 seconds)."
3. `curl -s "http://fastapi:8000/api/jobs/start/analyze?edoc_id=abc123&wait=true&timeout=120"` → returns full result
4. Send analysis results to user

**Example 2: "Create infographic for FRT"**

1. `curl -s http://fastapi:8000/api/analyze/notebooks` → find FRT notebook_id
2. **SEND NOW:** "⏳ Generating infographic for FRT via NotebookLM... Results will be sent shortly (about 30-60 seconds)."
3. `curl -s "http://fastapi:8000/api/jobs/start/infographic?notebook_id=abc&language=vi&wait=true&timeout=120"` → returns full result
4. Send infographic image to user
