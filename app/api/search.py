"""Google Search API — search Vietnamese stock news via SerpAPI."""

import os

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.config import SERPAPI_API_KEY

router = APIRouter(prefix="/api/search", tags=["search"])

SERPAPI_BASE_URL = "https://serpapi.com/search.json"

DEFAULT_LOCATION = "Ho Chi Minh City, Ho Chi Minh City, Vietnam"
DEFAULT_GOOGLE_DOMAIN = "google.com.vn"
DEFAULT_COUNTRY = "vn"


@router.get("")
async def google_search(
    query: str = Query(..., description="Search query (e.g. ticker symbols, keywords)"),
    search_type: str = Query("nws", description="Search type: nws (news), search (web), isch (images)"),
    num: int = Query(10, description="Number of results", ge=1, le=100),
    location: str = Query(DEFAULT_LOCATION, description="Search location"),
):
    """Search Google via SerpAPI. Defaults to Google News for Vietnamese stocks."""
    api_key = SERPAPI_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="SERPAPI_API_KEY not configured")

    params = {
        "api_key": api_key,
        "engine": "google",
        "q": query,
        "location": location,
        "google_domain": DEFAULT_GOOGLE_DOMAIN,
        "gl": DEFAULT_COUNTRY,
        "no_cache": "true",
        "num": str(num),
    }

    if search_type != "search":
        params["tbm"] = search_type

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(SERPAPI_BASE_URL, params=params)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"SerpAPI error: {response.text[:500]}",
        )

    data = response.json()

    if search_type == "nws":
        return _format_news_results(data, query)

    return _format_web_results(data, query)


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
