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
Every analysis, summary, detail, target price, recommendation, or question about a report
MUST go through the analyze API. This downloads the actual PDF and processes it through
Google NotebookLM for accurate, source-grounded answers.

- User asks "what does the FRT report say?" → start analysis job
- User asks "target price for VCB?" → start analysis job with the question
- **Do NOT** summarize, paraphrase, or infer report content on your own
- User mentions "NotebookLM" or "notebook" → start analysis job (100%, no exceptions)

### List available reports

When the user asks about reports, latest reports, "báo cáo", research, or analyst recommendations:

1. Use `web_fetch` to get the report list:
   ```
   web_fetch("http://fastapi:8000/api/reports")
   ```

2. Show reports as a numbered list:
   ```
   #1 [FRT] ABS - Báo cáo cổ phiếu FRT... (06/03/2026) [CafeF]
   #2 [VCB] KBSV - VCB Tăng trưởng... (05/03/2026) [CafeF]
   ```

### Analyze a report (async job pattern)

Analysis takes 30-60+ seconds. You MUST follow this 3-step pattern:

**Step 1: Start the job and tell the user immediately**

Submit the analysis job (POST — requires exec). It returns instantly with a `job_id`:
```
curl -s -X POST http://fastapi:8000/api/analyze -H "Content-Type: application/json" -d '{"edoc_id": "<edoc_id>"}'
```
Or with a custom question:
```
curl -s -X POST http://fastapi:8000/api/analyze -H "Content-Type: application/json" -d '{"edoc_id": "<edoc_id>", "question": "<question>"}'
```

Send the user an immediate message:
```
⏳ Đang phân tích báo cáo [title] qua NotebookLM... Kết quả sẽ được gửi khi hoàn tất (30-60 giây).
```

**Step 2: Poll for results**

Wait ~30 seconds, then check the job status using `web_fetch` (no exec needed):
```
web_fetch("http://fastapi:8000/api/analyze/status/<job_id>")
```

Check the `status` field:
- `"pending"` or `"running"` → wait 15 more seconds, poll again
- `"completed"` → the `answer` field has the results
- `"failed"` → the `error` field explains what went wrong

**Step 3: Deliver the results**

Send the analysis results to the user as a follow-up message.
If the job failed, tell the user what went wrong.

### CRITICAL: Never leave the user without results

- **Always poll** until the job completes or fails. Do NOT abandon the job.
- **Always send results** back to the user, even if it takes multiple polls.
- If you get distracted by another message, come back and check the job status.

### Fetch new reports

When asked to refresh, fetch new, or update reports (POST — requires exec):
```
curl -s -X POST http://fastapi:8000/api/reports/fetch
```

### Example flow

User: "Phân tích báo cáo FRT"

1. `web_fetch("http://fastapi:8000/api/reports")` → find FRT report, get edoc_id
2. `curl -s -X POST http://fastapi:8000/api/analyze -H "Content-Type: application/json" -d '{"edoc_id": "abc123"}'` → get job_id "f7a2b1c3"
3. Send: "⏳ Đang phân tích báo cáo FRT qua NotebookLM... Kết quả sẽ được gửi khi hoàn tất."
4. Wait 30s → `web_fetch("http://fastapi:8000/api/analyze/status/f7a2b1c3")` → status: "running"
5. Wait 15s → `web_fetch("http://fastapi:8000/api/analyze/status/f7a2b1c3")` → status: "completed", answer: "..."
6. Send the analysis results to the user.
