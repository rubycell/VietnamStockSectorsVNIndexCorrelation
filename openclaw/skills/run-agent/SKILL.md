---
name: run-agent
description: Run a specific AI agent by name or ID
---

## Instructions

When asked to run an agent (e.g., "run the trendy sector detector", "check unusual volume"):

## ⚠️ MANDATORY: Send acknowledgment IMMEDIATELY, BEFORE the blocking call.

1. First, list available agents:
   ```
   curl -s http://fastapi:8000/api/agents
   ```
2. Find the matching agent by name or ID.

3. **IMMEDIATELY send this message (BEFORE the blocking call):**
   ```
   ⏳ Running agent [AGENT_NAME]... Results will be sent when complete.
   ```

4. Execute the agent (blocks until done, no polling needed):
   ```
   curl -s "http://fastapi:8000/api/jobs/start/execute-agent/<AGENT_ID>?wait=true&timeout=180"
   ```
   This returns the full result. **Do NOT poll.**

5. Present the results clearly. If the agent found insights, highlight them.
6. If the agent failed, report the error.
