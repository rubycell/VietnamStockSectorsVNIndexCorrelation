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
MUST go through the analyze_report API endpoint. This endpoint downloads the actual PDF and
processes it through Google NotebookLM for accurate, source-grounded answers.

- User asks "what does the FRT report say?" → call analyze_report API with the edoc_id
- User asks "target price for VCB?" → call analyze_report API with the question
- User asks a follow-up about the same report → call analyze_report API again with the new question
- **Do NOT** summarize, paraphrase, or infer report content on your own
- User mentions "NotebookLM" or "notebook" → call analyze_report API (100%, no exceptions)

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
   Include: number, ticker, broker source, title, date, and whether from Vietstock or CafeF.

### Analyze a specific report (default summary)

When the user asks to analyze a report without a specific question:

1. First list reports if not already shown.
2. Map user's choice to `edoc_id` from the list.
3. Call the analyze endpoint (POST — requires exec):
   ```
   curl -s -X POST http://fastapi:8000/api/analyze -H "Content-Type: application/json" -d '{"edoc_id": "<edoc_id>"}'
   ```
4. Present the AI-generated analysis to the user.
5. Warn: analysis may take 30-60 seconds (NotebookLM processes the PDF).

### Ask a custom question about a report

When the user asks a specific question about a report:

1. Map the report reference to `edoc_id`.
2. Extract the user's question.
3. Call the analyze endpoint (POST — requires exec):
   ```
   curl -s -X POST http://fastapi:8000/api/analyze -H "Content-Type: application/json" -d '{"edoc_id": "<edoc_id>", "question": "<user_question>"}'
   ```
   The `question` field accepts any text. If the user asks in Vietnamese, pass the question in Vietnamese.
4. Present the answer clearly.

### Fetch new reports

When asked to refresh, fetch new, or update reports (POST — requires exec):

```
curl -s -X POST http://fastapi:8000/api/reports/fetch
```
This scrapes both Vietstock and CafeF for new reports.

### Example conversations

- "Show me latest reports" → `web_fetch("http://fastapi:8000/api/reports")`
- "reports" → `web_fetch("http://fastapi:8000/api/reports")`
- "báo cáo mới" → `web_fetch("http://fastapi:8000/api/reports")`
- "Analyze report #3" → `curl -s -X POST http://fastapi:8000/api/analyze ...`
- "Fetch new reports" → `curl -s -X POST http://fastapi:8000/api/reports/fetch`
