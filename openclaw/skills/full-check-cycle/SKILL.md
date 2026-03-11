---
name: full-check-cycle
description: Run the complete trading check cycle — fetch prices, update portfolio, detect swing lows, evaluate rules, and run scheduled agents
---

## Instructions

When asked to run a check cycle, market check, or hourly check:

1. Start the check cycle job (returns instantly with job_id):
   ```
   curl -s http://fastapi:8000/api/jobs/start/check-cycle
   ```

2. Tell the user: "⏳ Running check cycle... This may take a minute."

3. Poll for results (wait ~30s, then check):
   ```
   curl -s http://fastapi:8000/api/jobs/<JOB_ID>
   ```
   - `"running"` → wait 15s, poll again
   - `"completed"` → read the `result` field
   - `"failed"` → report the error

4. Summarize the results for the user:
   - List any triggered trading rules with their alert messages
   - Report any agent errors
   - If no rules triggered, say "All clear — no rules triggered this cycle"

5. If critical alerts exist (rules #4 or #9), format them prominently.
