"""Google Search API — search Vietnamese stock news via SerpAPI."""

import asyncio
import re
from datetime import date, datetime, timedelta

import serpapi
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import SERPAPI_API_KEY
from app.main import get_database_session

router = APIRouter(prefix="/api/search", tags=["search"])
dates_router = APIRouter(prefix="/api", tags=["dates"])


def _last_business_day(reference: date) -> date:
    """Return the most recent business day before reference (Mon–Fri, no holiday logic)."""
    offset = 1 if reference.weekday() != 0 else 3  # Monday needs 3-day lookback to Friday
    return reference - timedelta(days=offset)


@dates_router.get("/market-date")
def market_date():
    """Return today and last business day in MM/DD/YYYY format for news date filtering."""
    today = date.today()
    last_business = _last_business_day(today)
    return {
        "today": today.strftime("%m/%d/%Y"),
        "last_business_day": last_business.strftime("%m/%d/%Y"),
    }


def _build_news_query(tickers: list[str], after_date_str: str | None) -> str:
    """Build a Google News query with quoted OR syntax and after: date filter.

    Example output: '"DGC" OR "DCM" OR "DPM" after:2026-03-16'
    Quoted tickers force exact matches — prevents missing tickers in multi-symbol queries.
    """
    quoted = " OR ".join(f'"{ticker}"' for ticker in tickers)
    if after_date_str:
        # Convert MM/DD/YYYY → YYYY-MM-DD for Google's after: operator
        parsed = datetime.strptime(after_date_str, "%m/%d/%Y")
        return f"{quoted} after:{parsed.strftime('%Y-%m-%d')}"
    return quoted


def _serpapi_search(query: str, num: int) -> dict:
    """Run a synchronous SerpAPI search (called via asyncio.to_thread)."""
    api_key = SERPAPI_API_KEY
    if not api_key:
        raise ValueError("SERPAPI_API_KEY not configured")

    client = serpapi.Client(api_key=api_key)
    return client.search({
        "engine": "google",
        "google_domain": "google.com.vn",
        "q": query,
        "gl": "vn",
        "hl": "vi",
        "location": "Vietnam",
        "no_cache": "true",
        "num": str(num),
        "tbm": "nws",
        "nfpr": "1",   # disable auto-correction / personalised results
        "filter": "0",  # disable duplicate-result filtering
    })


@router.get("")
async def google_search(
    query: str = Query(..., description="Space-separated ticker symbols or a raw query string"),
    search_type: str = Query("nws", description="Search type: nws (news), search (web)"),
    num: int = Query(10, description="Number of results", ge=1, le=100),
    after_date: str = Query(None, description="Filter results after this date (MM/DD/YYYY)"),
    before_date: str = Query(None, description="Filter results before this date (MM/DD/YYYY) — informational only"),
):
    """Search Google News via SerpAPI with exact-match quoted OR syntax for tickers."""
    if not SERPAPI_API_KEY:
        raise HTTPException(status_code=500, detail="SERPAPI_API_KEY not configured")

    if search_type == "nws":
        tickers = query.split()
        search_query = _build_news_query(tickers, after_date)
    else:
        search_query = query

    try:
        data = await asyncio.to_thread(_serpapi_search, search_query, num)
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"SerpAPI error: {error}")

    if search_type == "nws":
        return _format_news_results(data, search_query)

    return _format_web_results(data, search_query)


def _format_news_results(data: dict, query: str) -> dict:
    """Extract and format news results from SerpAPI response."""
    news_results = data.get("news_results", [])
    return {
        "query": query,
        "type": "news",
        "count": len(news_results),
        "results": [
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "source": item.get("source", ""),
                "date": item.get("date", ""),
                "snippet": item.get("snippet", ""),
                "thumbnail": item.get("thumbnail", ""),
            }
            for item in news_results
        ],
    }


def _format_web_results(data: dict, query: str) -> dict:
    """Extract and format organic web results from SerpAPI response."""
    organic_results = data.get("organic_results", [])
    return {
        "query": query,
        "type": "web",
        "count": len(organic_results),
        "results": [
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "position": item.get("position", 0),
            }
            for item in organic_results
        ],
    }


def _title_word_set(title: str) -> set[str]:
    """Lowercase, strip punctuation, return words longer than 2 chars."""
    words = re.sub(r"[^\w\s]", "", title.lower()).split()
    return {word for word in words if len(word) > 2}


def _jaccard_similarity(title_a: str, title_b: str) -> float:
    """Word-set Jaccard similarity between two article titles (0.0–1.0)."""
    words_a = _title_word_set(title_a)
    words_b = _title_word_set(title_b)
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _dedup_news(articles: list[dict], similarity_threshold: float = 0.55) -> list[dict]:
    """Remove near-duplicate articles that cover the same event.

    When two articles exceed the similarity threshold, keep the one with the
    longer snippet (more informative). O(n²) — acceptable for <100 articles.
    """
    unique: list[dict] = []
    for candidate in articles:
        duplicate_index = None
        for index, existing in enumerate(unique):
            if _jaccard_similarity(candidate["title"], existing["title"]) >= similarity_threshold:
                duplicate_index = index
                break
        if duplicate_index is None:
            unique.append(candidate)
        elif len(candidate.get("snippet", "")) > len(unique[duplicate_index].get("snippet", "")):
            unique[duplicate_index] = candidate  # replace with more informative version
    return unique


@router.get("/combined")
async def search_news_combined(
    after_date: str = Query(None, description="Filter results after this date (MM/DD/YYYY)"),
    session: Session = Depends(get_database_session),
):
    """Run all portfolio/watchlist search groups in parallel, deduplicate, return combined results.

    Replaces the manual loop of get-groups → search-each → collect in the bot workflow.
    Runs all SerpAPI calls concurrently then removes near-duplicate articles by title similarity.
    """
    from app.api.search_groups import (
        _group_tickers_by_sector,
        _load_sector_map,
        _pack_into_query_groups,
        _recommended_num_results,
    )
    from app.models import Holding, WatchlistItem

    portfolio_tickers = [holding.ticker for holding in session.query(Holding).all()]
    watchlist_tickers = [item.ticker for item in session.query(WatchlistItem).all()]
    all_tickers = list(dict.fromkeys(portfolio_tickers + watchlist_tickers))

    if not all_tickers:
        raise HTTPException(status_code=404, detail="No tickers in portfolio or watchlist")

    sector_map = _load_sector_map()
    sector_groups = _group_tickers_by_sector(all_tickers, sector_map)
    query_groups = _pack_into_query_groups(sector_groups)

    async def _search_one_group(group: list[str]) -> list[dict]:
        query = _build_news_query(group, after_date)
        num = _recommended_num_results(len(group))
        try:
            data = await asyncio.to_thread(_serpapi_search, query, num)
            return _format_news_results(data, query)["results"]
        except Exception:
            return []

    results_per_group = await asyncio.gather(*[_search_one_group(group) for group in query_groups])
    all_articles = [article for group_articles in results_per_group for article in group_articles]
    deduped_articles = _dedup_news(all_articles)

    return {
        "groups_searched": len(query_groups),
        "total_raw": len(all_articles),
        "total_after_dedup": len(deduped_articles),
        "after_date": after_date,
        "results": deduped_articles,
    }
