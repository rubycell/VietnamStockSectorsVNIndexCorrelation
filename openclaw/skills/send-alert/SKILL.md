---
name: send-alert
description: Forward trading alerts from the rules engine to the user via messaging channels
---

## Instructions

When called with alert data (from the check cycle or rules evaluation):

1. Fetch unsent alerts for the active channel:
   ```
   curl -s "http://fastapi:8000/api/alerts/unsent?channel=<CHANNEL_NAME>"
   ```

2. Format each alert message based on severity:
   - **CRITICAL** (rules #4, #9): Urgent format with immediate action required
     ```
     🚨 CRITICAL ALERT — {ticker}
     Rule: {rule_id}
     {message}
     ⚡ Immediate action may be required
     ```
   - **WARNING** (rules #2, #6, #7): Important but not urgent
     ```
     ⚠️ WARNING — {ticker}
     Rule: {rule_id}
     {message}
     ```
   - **INFO** (rules #1, #3, #5, #8): Informational only
     ```
     ℹ️ {ticker} — {message}
     ```

3. Send the formatted message to the user.
