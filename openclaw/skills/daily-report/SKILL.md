---
name: daily-report
description: Generate and send a daily portfolio summary with alerts and P&L
---

## Instructions

When triggered by the daily cron or when asked for a daily report:

1. Fetch portfolio summary:
   ```
   curl {env:FASTAPI_URL}/api/portfolio
   ```

2. Fetch today's alerts:
   ```
   curl "{env:FASTAPI_URL}/api/alerts?limit=50"
   ```

3. Fetch and run rules evaluation to catch any end-of-day triggers:
   ```
   curl -X POST {env:FASTAPI_URL}/api/rules/evaluate
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
