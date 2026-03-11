---
name: daily-report
description: Generate and send a daily portfolio summary with alerts and P&L
---

## Instructions

When triggered by the daily cron or when asked for a daily report:

1. Use `web_fetch` to get the portfolio summary:
   ```
   web_fetch("http://fastapi:8000/api/portfolio")
   ```

2. Use `web_fetch` to get today's alerts:
   ```
   web_fetch("http://fastapi:8000/api/alerts")
   ```

3. Evaluate end-of-day rules (POST — requires exec):
   ```
   curl -s -X POST http://fastapi:8000/api/rules/evaluate
   ```

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
