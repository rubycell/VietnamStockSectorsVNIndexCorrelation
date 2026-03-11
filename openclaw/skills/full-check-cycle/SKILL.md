---
name: full-check-cycle
description: Run the complete trading check cycle — fetch prices, update portfolio, detect swing lows, evaluate rules, and run scheduled agents
---

## Instructions

When asked to run a check cycle, market check, or hourly check:

## ⚠️ MANDATORY: Send acknowledgment IMMEDIATELY, BEFORE the blocking call.

1. **IMMEDIATELY send this message to the user FIRST:**
   ```
   ⏳ Running check cycle... Results will be sent when complete (about 1-2 minutes).
   ```

2. Run the check cycle (blocks until done, no polling needed):
   ```
   curl -s "http://fastapi:8000/api/jobs/start/check-cycle?wait=true&timeout=300"
   ```
   This returns the full result when the job completes. **Do NOT poll.**

3. Summarize the results for the user:
   - List any triggered trading rules with their alert messages
   - Report any agent errors
   - If no rules triggered, say "All clear — no rules triggered this cycle"

4. If critical alerts exist (rules #4 or #9), format them prominently.
