---
name: full-check-cycle
description: Run the complete trading check cycle — fetch prices, update portfolio, detect swing lows, evaluate rules, and run scheduled agents
---

## Instructions

When asked to run a check cycle, market check, or hourly check:

1. Run the check cycle (POST — requires exec):
   ```
   curl -s -X POST http://fastapi:8000/api/check-cycle
   ```

2. Parse the JSON response. It contains:
   - `success`: whether the cycle completed
   - `results`: per-agent results
   - `errors`: any agent failures

3. Summarize the results for the user:
   - List any triggered trading rules with their alert messages
   - Report any agent errors
   - If no rules triggered, say "All clear — no rules triggered this cycle"

4. If critical alerts exist (rules #4 or #9), format them prominently.
