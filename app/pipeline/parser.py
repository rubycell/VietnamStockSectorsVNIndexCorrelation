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


def parse_tcbs_xlsx(file: BinaryIO) -> pd.DataFrame:
    """Parse a TCBS trade history XLSX into a normalized DataFrame.

    - Reads from row 15 (header_row=14 in 0-indexed)
    - Maps Vietnamese column names to English
    - Filters footer/total rows
    - Ensures order_no is string type
    """
    file.seek(0)

    # Read with header at row 14 (0-indexed), order_no as string to preserve hex IDs
    dataframe = pd.read_excel(
        file,
        header=14,
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
