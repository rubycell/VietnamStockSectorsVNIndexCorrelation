"""Parse TCBS 'Lich su giao dich co phieu' XLSX exports."""

from typing import BinaryIO

import openpyxl
import pandas as pd

COLUMN_MAP = {
    "Mã CP": "ticker",
    "Ngày GD": "trading_date",
    "Giao dịch": "trade_side",
    "KL đặt": "order_volume",
    "Giá đặt": "order_price",
    "KL khớp": "matched_volume",
    "Giá khớp": "matched_price",
    "Giá trị khớp": "matched_value",
    "Phí": "fee",
    "Thuế": "tax",
    "Giá vốn": "cost_basis",
    "Lãi lỗ": "return_pnl",
    "Kênh GD": "channel",
    "Trạng thái": "status",
    "Loại lệnh": "order_type",
    "Số hiệu lệnh": "order_no",
}

FOOTER_MARKERS = {"Tổng", "Ngày xuất báo cáo", "Report Date", "Chú thích", "Total"}


def extract_account_type(file: BinaryIO) -> str:
    """Read the account type from TCBS header rows.

    Row 10 (0-indexed row 9) contains account type info.
    Returns 'margin', 'normal', or 'unknown'.
    """
    file.seek(0)
    workbook = openpyxl.load_workbook(file, read_only=True, data_only=True)
    worksheet = workbook.active

    for _row_index, row in enumerate(worksheet.iter_rows(min_row=1, max_row=15, values_only=True)):
        cell_text = str(row[0]) if row[0] else ""
        if "Ký quỹ" in cell_text or "Ky quy" in cell_text:
            workbook.close()
            file.seek(0)
            return "margin"
        if "Thường" in cell_text or "Thuong" in cell_text:
            workbook.close()
            file.seek(0)
            return "normal"

    workbook.close()
    file.seek(0)
    return "unknown"


def _detect_header_row(file: BinaryIO) -> int:
    """Auto-detect the header row by scanning for known column names.

    Scans the first 30 rows looking for a row that contains at least 3
    of our known Vietnamese column names (e.g. 'Mã CP', 'Ngày GD').
    Returns the 0-indexed row number, defaults to 14 if not found.
    """
    file.seek(0)
    workbook = openpyxl.load_workbook(file, read_only=True, data_only=True)
    worksheet = workbook.active

    known_headers = set(COLUMN_MAP.keys())

    for row_index, row in enumerate(worksheet.iter_rows(
        min_row=1, max_row=30, values_only=True
    )):
        cell_values = {str(cell).strip() for cell in row if cell is not None}
        matches = cell_values & known_headers
        if len(matches) >= 3:
            workbook.close()
            file.seek(0)
            return row_index

    workbook.close()
    file.seek(0)
    return 14  # fallback to original default


def parse_tcbs_xlsx(file: BinaryIO) -> pd.DataFrame:
    """Parse a TCBS trade history XLSX into a normalized DataFrame.

    - Auto-detects header row by scanning for Vietnamese column names
    - Maps Vietnamese column names to English
    - Filters footer/total rows
    - Ensures order_no is string type
    """
    file.seek(0)

    header_row = _detect_header_row(file)

    # Read with auto-detected header, order_no as string to preserve hex IDs
    dataframe = pd.read_excel(
        file,
        header=header_row,
        dtype={"Số hiệu lệnh": str},
        engine="openpyxl",
    )

    # Rename columns from Vietnamese to English
    dataframe = dataframe.rename(
        columns={key: value for key, value in COLUMN_MAP.items() if key in dataframe.columns}
    )

    # Keep only mapped columns that exist
    valid_columns = [value for value in COLUMN_MAP.values() if value in dataframe.columns]
    dataframe = dataframe[valid_columns]

    # Filter footer rows: remove NaN tickers and rows matching footer markers
    if "ticker" in dataframe.columns:
        dataframe = dataframe[dataframe["ticker"].notna()]
        dataframe = dataframe[
            ~dataframe["ticker"].astype(str).str.strip().isin(FOOTER_MARKERS)
        ]
        dataframe = dataframe[
            ~dataframe["ticker"]
            .astype(str)
            .str.contains("Ngày xuất|Report Date|Chú thích", na=False)
        ]

    # Ensure order_no is string
    if "order_no" in dataframe.columns:
        dataframe["order_no"] = dataframe["order_no"].astype(str).str.strip()

    dataframe = dataframe.reset_index(drop=True)
    return dataframe
