"""Fetch ALL available VN30F1M candle data using vnstock.

KBS API Guest limits:
- 20 requests/minute (but vnstock retries internally, consuming extra quota)
- Single request may cap rows, so we chunk by month
- Scans back 5 years; skips empty periods automatically
"""

import sys
import time
from datetime import datetime, timedelta

import pandas as pd
from vnstock import Vnstock

SYMBOL = "VN30F1M"
INTERVAL = "15m"
OUTPUT_PATH = "data/VN30F1M_15m.csv"
# 8 seconds accounts for vnstock's internal retries eating extra quota
SLEEP_BETWEEN_REQUESTS = 8
# After N consecutive empty chunks before finding any data, skip forward
SKIP_AFTER_EMPTIES = 3


def generate_monthly_ranges(start_date: str, end_date: str) -> list[tuple[str, str]]:
    """Generate non-overlapping monthly (start, end) date pairs."""
    ranges = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current < end:
        month_end = current + timedelta(days=30)
        if month_end > end:
            month_end = end
        ranges.append((current.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d")))
        current = month_end + timedelta(days=1)

    return ranges


def fetch_chunk(futures, chunk_start: str, chunk_end: str) -> pd.DataFrame | None:
    """Fetch a single chunk, handling rate limit gracefully."""
    for attempt in range(3):
        try:
            df = futures.quote.history(
                start=chunk_start, end=chunk_end, interval=INTERVAL
            )
            if df is not None and not df.empty:
                return df
            return None
        except SystemExit:
            # vnstock calls sys.exit on rate limit — catch and wait
            wait = 15 * (attempt + 1)
            print(f"    Rate limited, waiting {wait}s (attempt {attempt + 1}/3)...")
            time.sleep(wait)
        except Exception:
            return None
    return None


def fetch_all() -> pd.DataFrame:
    """Fetch all available data in monthly chunks with rate limiting and smart skipping."""
    vn = Vnstock(source="KBS", show_log=False)
    futures = vn.stock(symbol=SYMBOL, source="KBS")

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")

    ranges = generate_monthly_ranges(start_date, end_date)
    all_chunks: list[pd.DataFrame] = []
    consecutive_empty = 0
    found_data = False

    print(f"Fetching {SYMBOL} {INTERVAL} candles")
    print(f"Scanning {start_date} to {end_date} ({len(ranges)} chunks max)")
    print(f"Sleep between requests: {SLEEP_BETWEEN_REQUESTS}s")
    print("-" * 60)

    i = 0
    while i < len(ranges):
        chunk_start, chunk_end = ranges[i]
        label = f"[{i + 1}/{len(ranges)}] {chunk_start} to {chunk_end}"

        df = fetch_chunk(futures, chunk_start, chunk_end)

        if df is not None:
            print(f"{label}: {len(df)} rows ({df['time'].min()} -> {df['time'].max()})")
            all_chunks.append(df)
            consecutive_empty = 0
            found_data = True
        else:
            consecutive_empty += 1

            if not found_data and consecutive_empty >= SKIP_AFTER_EMPTIES:
                # No data this far back — halve remaining distance to present
                remaining = len(ranges) - i
                skip_count = remaining // 2
                if skip_count > 1:
                    print(f"{label}: no data — skipping {skip_count} chunks forward")
                    i += skip_count
                    consecutive_empty = 0
                    continue
                else:
                    print(f"{label}: no data (empty)")
            else:
                print(f"{label}: no data (empty)")

        i += 1
        if i < len(ranges):
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    if not all_chunks:
        print("No data retrieved!")
        return pd.DataFrame()

    combined = pd.concat(all_chunks, ignore_index=True)
    combined = combined.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)

    print("-" * 60)
    print(f"Total unique rows: {len(combined)}")
    print(f"Full range: {combined['time'].min()} to {combined['time'].max()}")

    return combined


def main() -> None:
    df = fetch_all()
    if df.empty:
        return

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} rows to {OUTPUT_PATH}")
    print()
    print(df.head(5))
    print("...")
    print(df.tail(5))


if __name__ == "__main__":
    main()
