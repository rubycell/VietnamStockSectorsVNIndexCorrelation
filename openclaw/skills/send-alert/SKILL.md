---
name: send-alert
description: Forward trading alerts from the rules engine to the user via Discord
---

## Instructions

When called with alert data (from the check cycle or rules evaluation):

1. Fetch unsent alerts for Discord:
   ```
   curl -s "http://fastapi:8000/api/alerts/unsent?channel=discord"
   ```

2. Format each alert message based on severity:
   - **CRITICAL** (rules #4, #9): Urgent format with immediate action required
     ```
     🚨 CRITICAL ALERT — {ticker}
     Rule: {rule_id}
     {message}
     ⚡ Immediate action may be required
     ```
   - **WARNING** (rules #2, #6, #8): Important but not urgent
     ```
     ⚠️ WARNING — {ticker}
     Rule: {rule_id}
     {message}
     ```
   - **INFO** (rules #7): Informational only
     ```
     ℹ️ {ticker} — {message}
     ```

3. Send the formatted message to the user via Discord.

4. After sending, mark each alert as sent:
   ```
   curl -s -X POST "http://fastapi:8000/api/alerts/{alert_id}/mark-sent" -H "Content-Type: application/json" -d '{"channel": "discord"}'
   ```
