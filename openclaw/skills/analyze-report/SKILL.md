---
name: analyze-report
description: >
  ALWAYS use this skill when the user mentions: "reports", "latest reports", "báo cáo",
  "phân tích báo cáo", "Vietstock", "CafeF", "research reports", "broker reports",
  "analyst reports", "PDF reports", "NotebookLM", "notebooklm", "notebook",
  or asks to analyze a stock ticker's research report.
  This skill fetches broker analysis reports from Vietstock and CafeF websites
  and analyzes them through Google NotebookLM.
---

## Instructions

**This skill handles ALL requests about broker/analyst research reports from Vietstock and CafeF.**

### CRITICAL RULE: Always use NotebookLM via the API

**NEVER answer questions about report content from your own knowledge.**
Every analysis MUST go through the analyze API. This downloads the actual PDF and processes it through Google NotebookLM.

- **Do NOT** summarize, paraphrase, or infer report content on your own
- User mentions "NotebookLM" or "notebook" → start analysis job (100%, no exceptions)

### List available reports

```
curl -s http://fastapi:8000/api/reports
```

Show as numbered list: `#1 [FRT] ABS - Báo cáo... (06/03/2026) [CafeF]`

### Analyze a report (async job pattern)

Analysis takes 30-60+ seconds. Follow this pattern:

**Step 1: Start the job** (returns instantly with job_id):
```
curl -s "http://fastapi:8000/api/jobs/start/analyze?edoc_id=<EDOC_ID>"
```
Or with a custom question:
```
curl -s "http://fastapi:8000/api/jobs/start/analyze?edoc_id=<EDOC_ID>&question=<URL_ENCODED_QUESTION>"
```

**Step 2: Tell the user immediately:**
```
⏳ Đang phân tích báo cáo [title] qua NotebookLM... Kết quả sẽ được gửi khi hoàn tất (30-60 giây).
```

**Step 3: Poll for results** (wait ~30s, then check):
```
curl -s http://fastapi:8000/api/jobs/<JOB_ID>
```
- `"status": "running"` → wait 15s, poll again
- `"status": "completed"` → the `result.answer` field has the analysis
- `"status": "failed"` → the `error` field explains what went wrong

**Step 4: Deliver results** to the user as a follow-up message.

### CRITICAL: Never leave the user without results

- **Always poll** until the job completes or fails
- **Always send results** back to the user
- If you get distracted by another message, come back and check the job

### Fetch new reports

Start the scraping job (returns instantly):
```
curl -s http://fastapi:8000/api/jobs/start/fetch-reports
```
Then poll `curl -s http://fastapi:8000/api/jobs/<JOB_ID>` for results.

### Example flow

User: "Phân tích báo cáo FRT"

1. `curl -s http://fastapi:8000/api/reports` → find FRT, get edoc_id
2. `curl -s "http://fastapi:8000/api/jobs/start/analyze?edoc_id=abc123"` → get job_id
3. Send: "⏳ Đang phân tích báo cáo FRT..."
4. Wait 30s → `curl -s http://fastapi:8000/api/jobs/<JOB_ID>` → running
5. Wait 15s → `curl -s http://fastapi:8000/api/jobs/<JOB_ID>` → completed
6. Send analysis results to user
