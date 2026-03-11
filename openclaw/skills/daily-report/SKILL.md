---
name: daily-report
description: Generate and send a daily portfolio summary with alerts and P&L
---

## Instructions

When triggered by the daily cron or when asked for a daily report:

1. Fetch the portfolio summary:
   ```
   curl -s http://fastapi:8000/api/portfolio
   ```

2. Fetch today's alerts:
   ```
   curl -s http://fastapi:8000/api/alerts
   ```

3. Start rules evaluation job:
   ```
   curl -s http://fastapi:8000/api/jobs/start/evaluate-rules
   ```
   Poll `curl -s http://fastapi:8000/api/jobs/<JOB_ID>` for results.

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
