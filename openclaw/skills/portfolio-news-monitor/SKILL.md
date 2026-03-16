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

### Step 2: Calculate last business day

Use this logic to set the date range context:
- Today is Tue–Fri → last business day = yesterday
- Today is Mon → last business day = last Friday
- Today is Sat → last business day = Friday
- Today is Sun → last business day = Friday

Mention this date in the NotebookLM analysis prompt.

### Step 3: Group tickers by sector and search

Group portfolio tickers by sector (from portfolio data). Combine all tickers in each sector into ONE search query — space-separated, just the ticker symbols.

**One search per sector, maximum 10 searches per day.**

For each sector group, search Google News Vietnam:

- **MCP:** `google_search` tool:
```json
{
  "query": "HPG FRT NLG",
  "search_type": "nws",
  "num": 10
}
```
- **Fallback:** `curl -s "http://fastapi:8000/api/search?query=HPG+FRT+NLG&search_type=nws&num=10"`

The query is just the ticker symbols separated by spaces. Nothing else.

### Step 4: Collect all news results

From each search, collect the results (title, snippet, source, date, link). Combine all results into one text block.

### Step 5: Analyze with NotebookLM

Pick the notebook for the relevant sector (or a general one). Use `notebook_chat` to ask NotebookLM to identify **causal negative news** — meaning events that *cause* harm to the company or sector fundamentals, NOT observations of market price movement.

- **MCP:** `notebook_chat` tool:
```json
{
  "notebook_id": "<sector_notebook_id>",
  "question": "Phân tích các tin tức sau đây về cổ phiếu trong danh mục.\n\nChỉ liệt kê tin có TÁC ĐỘNG NHÂN QUẢ trực tiếp đến doanh nghiệp hoặc ngành, ví dụ:\n- Chính sách/quy định mới ảnh hưởng trực tiếp (thuế quan, hạn chế xuất khẩu, thay đổi luật)\n- Kết quả kinh doanh xấu (doanh thu giảm, lỗ, nợ xấu tăng)\n- Sự cố vận hành, pháp lý, lãnh đạo\n- Biến động giá nguyên liệu đầu vào hoặc thị trường xuất khẩu\n\nTUYỆT ĐỐI BỎ QUA các tin sau (đây là quan sát thị trường, không phải nguyên nhân):\n- Áp lực bán, chốt lời, dòng tiền yếu\n- Khối ngoại bán ròng hoặc mua ròng\n- Cổ phiếu kéo giảm VN-Index\n- Tâm lý thị trường tiêu cực hoặc tích cực\n- Bất kỳ mô tả nào về diễn biến giá hoặc thanh khoản\n\nNếu một tin chỉ mô tả điều gì đó đã xảy ra với giá cổ phiếu — hãy bỏ qua.\nChỉ giữ lại tin mà nếu cổ phiếu tăng giá hôm nay thì tin đó vẫn quan trọng.\n\n[PASTE ALL NEWS RESULTS HERE]"
}
```

If no notebook exists for that sector, skip NotebookLM and apply the same filtering criteria manually when summarizing news in your response.

**After analysis, before reporting:** Re-read each item you are about to report. Ask yourself: "Does this describe a market price movement, or does it describe an external event causing harm?" If it describes price movement (selling, declining, pressure, outflow), discard it.

### Step 6: Report

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
