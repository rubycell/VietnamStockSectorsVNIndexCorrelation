---
name: daily-report
description: Generate and send a daily portfolio summary with alerts and P&L
---

## Instructions

When triggered by the daily cron or when asked for a daily report:

## ⚠️ MANDATORY: Send acknowledgment IMMEDIATELY, BEFORE any blocking calls.

1. **IMMEDIATELY send this message (BEFORE any API calls):**
   ```
   ⏳ Generating daily report... Results will be sent when complete.
   ```

2. Fetch portfolio summary and today's alerts:
   - **MCP:** Use `get_portfolio` tool, then `list_alerts` tool
   - **Fallback:** `curl -s http://fastapi:8000/api/portfolio && echo "---SEPARATOR---" && curl -s http://fastapi:8000/api/alerts`

3. Run rules evaluation (blocks until done, no polling needed):
   - **MCP:** Use the `evaluate_rules` tool
   - **Fallback:** `curl -s "http://fastapi:8000/api/jobs/start/evaluate-rules?wait=true&timeout=120"`
   This returns the full result. **Do NOT poll.**

4. Compose a daily report with:
   - **Portfolio Overview**: Total value, total unrealized P&L, number of holdings
   - **Top Movers**: Holdings with largest unrealized P&L change (positive and negative)
   - **Alerts Summary**: Count of alerts by severity (CRITICAL, WARNING, INFO)
   - **Critical Alerts**: Full details for any CRITICAL alerts
   - **Rules Triggered**: Summary of rules evaluation results

5. Format the report clearly with sections and emoji indicators:
   - Use red indicators for losses and critical alerts
   - Use green indicators for gains
   - Keep the report concise — aim for under 500 words

6. Send the report to the user via the active channel.
