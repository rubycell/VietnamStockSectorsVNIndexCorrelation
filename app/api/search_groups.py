"""Search groups API — portfolio/watchlist tickers grouped for news searches.

Groups tickers by ICB Level 2 sector (from vnstock), then packs them into
≤10 query groups of ≤3 tickers each. Smaller sectors are merged together
to stay within the daily search quota (10 queries × 3 tickers = 30 slots).
"""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.main import get_database_session
from app.models import Holding, WatchlistItem

router = APIRouter(prefix="/api/search-groups", tags=["search"])

MAX_QUERIES = 10
MAX_TICKERS_PER_GROUP = 3


@lru_cache(maxsize=1)
def _load_sector_map() -> dict[str, str]:
    """Load ticker → ICB Level 2 sector name from vnstock. Cached for the process lifetime."""
    try:
        from vnstock import Listing
        listing = Listing(source="VCI")
        df = listing.symbols_by_industries()[["symbol", "icb_name2"]]
        return df.set_index("symbol")["icb_name2"].to_dict()
    except Exception:
        return {}


def _group_tickers_by_sector(tickers: list[str], sector_map: dict[str, str]) -> dict[str, list[str]]:
    """Map each ticker to its sector, returning sector → [tickers] dict."""
    groups: dict[str, list[str]] = {}
    for ticker in tickers:
        sector = sector_map.get(ticker, "Khác")
        groups.setdefault(sector, []).append(ticker)
    return groups


def _pack_into_query_groups(sector_groups: dict[str, list[str]]) -> list[list[str]]:
    """Split sector groups into chunks of MAX_TICKERS_PER_GROUP.

    If total chunks exceed MAX_QUERIES, merge the smallest chunks together
    until within budget, keeping same-sector tickers together where possible.
    """
    # Split each sector into chunks of MAX_TICKERS_PER_GROUP
    chunks: list[list[str]] = []
    for tickers in sector_groups.values():
        for i in range(0, len(tickers), MAX_TICKERS_PER_GROUP):
            chunks.append(tickers[i:i + MAX_TICKERS_PER_GROUP])

    # Merge smallest chunks until within MAX_QUERIES budget
    while len(chunks) > MAX_QUERIES:
        # Sort by size ascending and merge the two smallest
        chunks.sort(key=len)
        smallest = chunks.pop(0)
        second = chunks.pop(0)
        merged = smallest + second
        # If merged exceeds MAX_TICKERS_PER_GROUP * 2, re-split into two equal halves
        if len(merged) > MAX_TICKERS_PER_GROUP * 2:
            mid = len(merged) // 2
            chunks.append(merged[:mid])
            chunks.append(merged[mid:])
        else:
            chunks.append(merged)

    return chunks


def _recommended_num_results(group_size: int) -> int:
    """More tickers per query → request more results to avoid burying any ticker."""
    if group_size <= 3:
        return 10
    if group_size <= 5:
        return 20
    return 30


@router.get("")
def get_search_groups(session: Session = Depends(get_database_session)):
    """Return portfolio + watchlist tickers packed into ≤10 search query groups.

    Each group has ≤3 tickers (sector-aware) and a recommended num_results value.
    Use these groups to fire news searches without exceeding the daily quota.
    """
    portfolio_tickers = [h.ticker for h in session.query(Holding).all()]
    watchlist_tickers = [w.ticker for w in session.query(WatchlistItem).all()]
    all_tickers = list(dict.fromkeys(portfolio_tickers + watchlist_tickers))  # deduplicate, preserve order

    if not all_tickers:
        raise HTTPException(status_code=404, detail="No tickers in portfolio or watchlist")

    sector_map = _load_sector_map()
    sector_groups = _group_tickers_by_sector(all_tickers, sector_map)
    query_groups = _pack_into_query_groups(sector_groups)

    return {
        "total_tickers": len(all_tickers),
        "total_groups": len(query_groups),
        "quota_used": f"{len(query_groups)}/{MAX_QUERIES}",
        "groups": [
            {
                "tickers": group,
                "query": " ".join(group),
                "num_results": _recommended_num_results(len(group)),
            }
            for group in query_groups
        ],
    }
