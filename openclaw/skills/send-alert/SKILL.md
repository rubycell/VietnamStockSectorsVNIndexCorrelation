---
name: send-alert
description: Forward trading alerts from the rules engine to the user via messaging channels
---

## Instructions

When called with alert data (from the check cycle or rules evaluation):

1. Receive the alert context containing:
   - `ticker`: The stock ticker
   - `rule_id`: Which rule triggered
   - `severity`: CRITICAL, WARNING, or INFO
   - `message`: The alert message

2. Format the alert message based on severity:
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

4. After sending, mark the alert as sent by calling:
   ```
   curl -X POST {env:FASTAPI_URL}/api/alerts/{alert_id}/mark-sent \
     -H "Content-Type: application/json" \
     -d '{"channel": "telegram"}'
   ```

5. Only send alerts that have not already been sent to the channel. Check `sent_telegram` or `sent_whatsapp` fields.
