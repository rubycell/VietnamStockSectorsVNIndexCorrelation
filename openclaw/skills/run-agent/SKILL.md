---
name: run-agent
description: Run a specific AI agent by name or ID
---

## Instructions

When asked to run an agent (e.g., "run the trendy sector detector", "check unusual volume"):

1. First, list available agents: `curl $FASTAPI_URL/api/agents`
2. Find the matching agent by name or ID
3. Execute it: `curl -X POST $FASTAPI_URL/api/agents/{agent_id}/execute -H "Content-Type: application/json" -d '{"variables": {}}'`
4. Present the results clearly. If the agent found insights, highlight them.
5. If the agent failed, report the error.
