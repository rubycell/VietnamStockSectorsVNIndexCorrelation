---
name: deliver-job-result
description: >
  Receives job completion results from the FastAPI backend via webhook
  and delivers them to the user on the appropriate chat channel.
  This skill is triggered automatically — NOT by user messages.
---

## Instructions

**This skill is called by the FastAPI backend webhook, NOT by users.**

When triggered, you receive a JSON payload describing a completed background job.
Your job: format the result and deliver it to the user.

---

## Payload format

The webhook message contains a JSON block like:

```json
{
  "job_id": "abc123",
  "job_type": "infographic",
  "status": "completed",
  "description": "Generating infographic from notebook xyz",
  "result": { ... },
  "error": null
}
```

---

## How to deliver results

### For completed jobs with file artifacts

Job types that produce files: `infographic`, `audio`, `video`, `slides`, `quiz`, `flashcards`

1. Extract `result.file_path` (or `result.html_path` for quiz/flashcards)
2. Build the download URL: `http://fastapi:8000/api/artifacts/download?file_path=<PATH>`
3. Send the file to the user using the **message tool** with the `media` parameter:

```json
{
  "action": "send",
  "message": "Your [JOB_TYPE] is ready:",
  "media": "http://fastapi:8000/api/artifacts/download?file_path=<PATH>"
}
```

### For completed jobs with text results

Job types that return text: `analyze`, `report`, `study_guide`, `notebook_summary`, `chat`, `research`, `mind_map`

1. Extract `result.answer` or `result.text` or `result.data`
2. Send as a message (truncate to 1900 chars if needed for Discord)

### For failed jobs

Send an error message:
```
Job [JOB_TYPE] failed: [ERROR]
```

---

## Formatting by job type

| Job type | Result field | Delivery method |
|----------|-------------|-----------------|
| `analyze` | `result.answer` | Text message |
| `infographic` | `result.file_path` | File via `media` |
| `audio` | `result.file_path` | File via `media` |
| `video` | `result.file_path` | File via `media` |
| `slides` | `result.file_path` | File via `media` |
| `quiz` | `result.html_path` | File via `media` |
| `flashcards` | `result.html_path` | File via `media` |
| `report` | `result.text` | Text message |
| `study_guide` | `result.text` | Text message |
| `notebook_summary` | `result.text` | Text message |
| `chat` | `result.answer` | Text message |
| `research` | `result.data` | Text message (summarize) |
| `mind_map` | `result.data` | Text message (format as outline) |
| `check-cycle` | result object | Text message (summarize) |
| `fetch-reports` | result object | Text message (count new reports) |

---

## Rules

- Do NOT ask the user any questions — just deliver the result
- Keep messages concise
- Always include the job type in the message header
- For file artifacts, ALWAYS use the `media` parameter — never just send a URL as text
