"""Clean and normalize parsed TCBS trade data."""

from datetime import date, datetime
from typing import Tuple

import pandas as pd


TRADE_SIDE_MAP = {
    "Mua": "BUY",
    "Bán": "SELL",
    "Ban": "SELL",
}


def clean_fills(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize a parsed TCBS DataFrame.

    - Converts trade_side from Vietnamese to BUY/SELL
    - Parses trading_date to Python date objects
    - Ensures numeric columns are proper types
    - Ensures order_no is string
    """
    result = dataframe.copy()

    # Normalize trade_side
    if "trade_side" in result.columns:
        result["trade_side"] = result["trade_side"].map(
            lambda raw_side: TRADE_SIDE_MAP.get(str(raw_side).strip(), str(raw_side).strip())
        )

    # Parse trading_date
    if "trading_date" in result.columns:
        result["trading_date"] = result["trading_date"].apply(_parse_date)

    # Numeric columns
    numeric_columns = [
        "order_volume", "order_price", "matched_volume", "matched_price",
        "matched_value", "fee", "tax", "cost_basis", "return_pnl",
    ]
    for column_name in numeric_columns:
        if column_name in result.columns:
            result[column_name] = pd.to_numeric(result[column_name], errors="coerce").fillna(0)

    # Ensure order_no is string
    if "order_no" in result.columns:
        result["order_no"] = result["order_no"].astype(str).str.strip()

    return result


def _parse_date(value) -> date:
    """Parse date from various TCBS formats."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()

    text = str(value).strip()
    for date_format in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {value}")


def validate_fills(dataframe: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split DataFrame into valid and invalid rows.

    Valid rows must have: non-empty ticker, trading_date, matched_volume > 0.
    Returns (valid_df, invalid_df).
    """
    required_columns = ["ticker", "trading_date", "matched_volume"]

    validity_mask = pd.Series(True, index=dataframe.index)
    for column_name in required_columns:
        if column_name in dataframe.columns:
            validity_mask &= dataframe[column_name].notna()
            if column_name == "matched_volume":
                validity_mask &= pd.to_numeric(
                    dataframe[column_name], errors="coerce"
                ).fillna(0) > 0
        else:
            validity_mask = pd.Series(False, index=dataframe.index)

    # Also check ticker is not empty string
    if "ticker" in dataframe.columns:
        validity_mask &= dataframe["ticker"].astype(str).str.strip().ne("")

    valid_rows = dataframe[validity_mask].reset_index(drop=True)
    invalid_rows = dataframe[~validity_mask].reset_index(drop=True)
    return valid_rows, invalid_rows
