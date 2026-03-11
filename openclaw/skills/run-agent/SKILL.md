---
name: run-agent
description: Run a specific AI agent by name or ID
---

## Instructions

When asked to run an agent (e.g., "run the trendy sector detector", "check unusual volume"):

1. First, list available agents:
   ```
   curl -s http://fastapi:8000/api/agents
   ```
2. Find the matching agent by name or ID.
3. Start the agent execution job (returns instantly):
   ```
   curl -s http://fastapi:8000/api/jobs/start/execute-agent/<AGENT_ID>
   ```
4. Poll for results:
   ```
   curl -s http://fastapi:8000/api/jobs/<JOB_ID>
   ```
5. Present the results clearly. If the agent found insights, highlight them.
6. If the agent failed, report the error.
