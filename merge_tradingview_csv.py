"""Merge overlapping TradingView CSV exports by deduplicating on timestamp.

Reads all CSV files in a given directory, concatenates them, removes
duplicate rows (by `time` column), sorts chronologically, and writes
a single merged output file.

Usage:
    python merge_tradingview_csv.py [INPUT_DIR] [OUTPUT_FILE] [GLOB_PATTERN]

Defaults:
    INPUT_DIR    = tradingview_data/vn30f1m
    OUTPUT_FILE  = tradingview_data/vn30f1m/VN30F1M_15m_merged.csv
    GLOB_PATTERN = *.csv

Examples:
    python merge_tradingview_csv.py tradingview_data/vn30f1m out.csv "*, 5_*.csv"
    python merge_tradingview_csv.py tradingview_data/vn30f1m out.csv "*, 15_*.csv"
"""

import sys
from pathlib import Path

import pandas as pd


def find_csv_files(input_dir: Path, pattern: str = "*.csv") -> list[Path]:
    """Return matching CSV files in the directory, sorted by name."""
    csv_files = sorted(input_dir.glob(pattern))
    if not csv_files:
        raise FileNotFoundError(f"No files matching '{pattern}' in {input_dir}")
    return csv_files


def load_and_concat(csv_files: list[Path]) -> pd.DataFrame:
    """Load each CSV and concatenate into a single DataFrame."""
    frames = []
    for path in csv_files:
        df = pd.read_csv(path)
        print(f"  Loaded {path.name}: {len(df):,} rows")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def merge_by_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate on `time`, keeping the first occurrence, then sort."""
    before = len(df)
    merged = (
        df.drop_duplicates(subset=["time"], keep="first")
          .sort_values("time")
          .reset_index(drop=True)
    )
    after = len(merged)
    print(f"  Rows before dedup: {before:,}")
    print(f"  Rows after dedup:  {after:,}")
    print(f"  Duplicates removed: {before - after:,}")
    return merged


def main() -> None:
    default_dir = Path("tradingview_data/vn30f1m")
    default_out = default_dir / "VN30F1M_15m_merged.csv"

    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else default_dir
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else default_out
    pattern = sys.argv[3] if len(sys.argv) > 3 else "*.csv"

    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory")
        sys.exit(1)

    print(f"Input directory: {input_dir}")
    print(f"Pattern: {pattern}")
    csv_files = [
        f for f in find_csv_files(input_dir, pattern)
        if f.resolve() != output_file.resolve()
    ]
    print(f"Found {len(csv_files)} CSV file(s):")

    combined = load_and_concat(csv_files)
    merged = merge_by_timestamp(combined)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_file, index=False)
    print(f"\nMerged output written to: {output_file}")
    print(f"Date range: {pd.to_datetime(merged['time'].iloc[0], unit='s')} → "
          f"{pd.to_datetime(merged['time'].iloc[-1], unit='s')}")


if __name__ == "__main__":
    main()
