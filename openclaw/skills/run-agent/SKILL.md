---
name: run-agent
description: Run a specific AI agent by name or ID
---

## Instructions

When asked to run an agent (e.g., "run the trendy sector detector", "check unusual volume"):

1. First, list available agents using `web_fetch`:
   ```
   web_fetch("http://fastapi:8000/api/agents")
   ```
2. Find the matching agent by name or ID.
3. Execute the agent (POST — requires exec):
   ```
   curl -s -X POST http://fastapi:8000/api/agents/<AGENT_ID>/execute
   ```
4. Present the results clearly. If the agent found insights, highlight them.
5. If the agent failed, report the error.
