---
name: portfolio-news-monitor
description: >
  Monitor portfolio tickers for bad news. Groups tickers by sector,
  searches Google News Vietnam (max 10 searches/day), analyzes
  bad-sentiment results via NotebookLM.
  Trigger: "check news", "tin xấu", "bad news", "news monitor", "kiểm tra tin"
---

## Workflow

### Step 1: Get portfolio tickers

- **MCP:** `get_portfolio` tool
- **Fallback:** `curl -s http://fastapi:8000/api/portfolio`

Extract all `holdings[].ticker` values.

### Step 2: Get today and last business day

Call the market-date endpoint — do not calculate dates yourself:

- **Fallback:** `curl -s http://fastapi:8000/api/market-date`

Response: `{ "today": "03/17/2026", "last_business_day": "03/14/2026" }`

Use `last_business_day` as `after_date` and `today` as `before_date` in every search call in Step 3.

### Step 3: Fetch all news (combined, deduplicated)

One call runs all search groups in parallel and returns deduplicated results:

- **Fallback:** `curl -s "http://fastapi:8000/api/search/combined?after_date=03/14/2026"`

Pass `last_business_day` from Step 2 as `after_date`. The backend groups tickers by sector, runs ≤10 searches concurrently, then removes near-duplicate articles (same event covered by multiple publishers) before returning.

Response:
```json
{
  "groups_searched": 8,
  "total_raw": 64,
  "total_after_dedup": 41,
  "results": [{ "title": "...", "snippet": "...", "source": "...", "date": "...", "link": "..." }]
}
```

Use `results` directly — no further deduplication needed.

### Step 4: Analyze with NotebookLM

Pick the notebook for the relevant sector (or a general one). Use `notebook_chat` to ask NotebookLM to identify **causal negative news** — meaning events that *cause* harm to the company or sector fundamentals, NOT observations of market price movement.

- **MCP:** `notebook_chat` tool:
```json
{
  "notebook_id": "<sector_notebook_id>",
  "question": "Phân tích các tin tức sau đây về cổ phiếu trong danh mục.\n\nChỉ liệt kê tin có TÁC ĐỘNG NHÂN QUẢ trực tiếp đến doanh nghiệp hoặc ngành, ví dụ:\n- Chính sách/quy định mới ảnh hưởng trực tiếp (thuế quan, hạn chế xuất khẩu, thay đổi luật)\n- Kết quả kinh doanh xấu (doanh thu giảm, lỗ, nợ xấu tăng)\n- Sự cố vận hành, pháp lý, lãnh đạo\n- Biến động giá nguyên liệu đầu vào hoặc thị trường xuất khẩu\n\nTUYỆT ĐỐI BỎ QUA các tin sau (đây là quan sát thị trường, không phải nguyên nhân):\n- Áp lực bán, chốt lời, dòng tiền yếu\n- Khối ngoại bán ròng hoặc mua ròng\n- Cổ phiếu kéo giảm VN-Index\n- Tâm lý thị trường tiêu cực hoặc tích cực\n- Bất kỳ mô tả nào về diễn biến giá hoặc thanh khoản\n\nNếu một tin chỉ mô tả điều gì đó đã xảy ra với giá cổ phiếu — hãy bỏ qua.\nChỉ giữ lại tin mà nếu cổ phiếu tăng giá hôm nay thì tin đó vẫn quan trọng.\n\n[PASTE ALL NEWS RESULTS HERE]"
}
```

If no notebook exists for that sector, skip NotebookLM and apply the same filtering criteria manually when summarizing news in your response.

**After analysis, before reporting:** Re-read each item you are about to report and apply ALL of the following checks — discard if ANY fails:

1. **Causation check**: Does this describe an external event causing harm, or just a market price movement (selling, pressure, outflow, divergence)? If price movement → discard.
2. **Freshness check**: Is the news dated within the last 14 days? If older → discard, unless the article explicitly describes a *new development* on an existing situation (e.g. a tariff rate being changed, a court ruling, a new earnings release).
3. **Ticker relevance check**: Does this event directly affect this specific ticker's business model? (e.g. a seafood tariff affects VHC but not FPT; an ETF rebalancing affects no ticker's fundamentals regardless of who is named) → If the connection is only through market flows or index mechanics, discard.
4. **Hallucination check**: Is there a real, named source with a specific article date in the search results? If the source is vague ("General News", "contextual assessment", no URL) → discard. Do not report news synthesized from background knowledge.

### Step 5: Report

Only report tickers with bad-sentiment news. Format:

```
📊 Tin tức danh mục — [last business day date]

🔴 [TICKER] — [headline summary]
   Nguồn: [source] | [date]

🔴 [TICKER] — [headline summary]
   Nguồn: [source] | [date]

✅ Không có tin xấu cho các mã còn lại.
```

If no bad news found across all sectors: "✅ Không phát hiện tin tiêu cực cho danh mục."
