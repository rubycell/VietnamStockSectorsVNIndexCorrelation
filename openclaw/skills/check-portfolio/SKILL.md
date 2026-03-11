---
name: check-portfolio
description: Check current portfolio holdings, P&L, and position status
---

## Instructions

When asked about portfolio, holdings, positions, or P&L:

1. Call: `curl $FASTAPI_URL/api/portfolio`

2. Format the response as a clear summary:
   - Total portfolio value and overall P&L
   - Per-ticker: shares held, average cost, current price, unrealized P&L %
   - Highlight any positions with > 10% loss

3. If asked about a specific ticker, filter to just that ticker.
