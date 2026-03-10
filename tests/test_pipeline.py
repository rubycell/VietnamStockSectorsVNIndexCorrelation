"""Tests for TCBS XLSX parser and cleaner."""

import pytest
import pandas as pd
from io import BytesIO
from datetime import date
from app.pipeline.parser import parse_tcbs_xlsx, extract_account_type
from app.pipeline.cleaner import clean_fills, validate_fills


def _make_fake_xlsx(account_label="Ký quỹ", rows=None):
    """Create a minimal fake XLSX matching TCBS format."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active

    # Pad first 9 rows
    for i in range(9):
        ws.append([""])

    # Row 10 (index 9): account type info
    ws.append([f"Loại tài khoản: {account_label}"])

    # Rows 11-14: more padding
    for i in range(4):
        ws.append([""])

    # Row 15: headers
    headers = ["Mã CP", "Ngày GD", "Giao dịch", "KL đặt", "Giá đặt",
               "KL khớp", "Giá khớp", "Giá trị khớp", "Phí", "Thuế",
               "Giá vốn", "Lãi lỗ", "Kênh GD", "Trạng thái", "Loại lệnh", "Số hiệu lệnh"]
    ws.append(headers)

    # Data rows
    if rows is None:
        rows = [
            ["FPT", "15/01/2025", "Mua", 100, 120000, 100, 120000, 12000000,
             17000, 0, 120000, 0, "Online", "Hoàn tất", "Lệnh thường", "ABC123"],
            ["VCB", "16/01/2025", "Bán", 50, 95000, 50, 95000, 4750000,
             6700, 4750, 92000, 150000, "Online", "Hoàn tất", "Lệnh thường", "DEF456"],
        ]
    for row in rows:
        ws.append(row)

    # Footer rows
    ws.append(["Tổng", "", "", "", "", 150, "", 16750000, 23700, 4750, "", 150000, "", "", "", ""])
    ws.append(["Ngày xuất báo cáo: 10/03/2025"])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_extract_account_type_margin():
    xlsx = _make_fake_xlsx("Ký quỹ")
    assert extract_account_type(xlsx) == "margin"


def test_extract_account_type_normal():
    xlsx = _make_fake_xlsx("Thường")
    assert extract_account_type(xlsx) == "normal"


def test_parse_tcbs_xlsx_returns_dataframe():
    xlsx = _make_fake_xlsx()
    df = parse_tcbs_xlsx(xlsx)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "ticker" in df.columns
    assert "order_no" in df.columns


def test_parse_filters_footer_rows():
    xlsx = _make_fake_xlsx()
    df = parse_tcbs_xlsx(xlsx)
    # Should not contain "Tổng" or footer text
    assert "Tổng" not in df["ticker"].values
    assert len(df) == 2


def test_clean_fills_normalizes():
    xlsx = _make_fake_xlsx()
    df = parse_tcbs_xlsx(xlsx)
    cleaned = clean_fills(df)
    assert cleaned.iloc[0]["trade_side"] == "BUY"
    assert cleaned.iloc[1]["trade_side"] == "SELL"
    assert isinstance(cleaned.iloc[0]["trading_date"], date)


def test_clean_fills_order_no_as_string():
    """OrderNo must always be string, not float."""
    xlsx = _make_fake_xlsx()
    df = parse_tcbs_xlsx(xlsx)
    cleaned = clean_fills(df)
    for val in cleaned["order_no"]:
        assert isinstance(val, str)


def test_validate_fills_rejects_missing_ticker():
    df = pd.DataFrame([{
        "ticker": None, "trading_date": "2025-01-15", "trade_side": "BUY",
        "matched_volume": 100, "matched_price": 120000, "matched_value": 12000000,
        "order_no": "X", "fee": 0, "tax": 0, "order_volume": 100, "order_price": 120000,
        "cost_basis": 120000, "return_pnl": 0, "channel": "Online",
        "status": "Done", "order_type": "Normal",
    }])
    valid, invalid = validate_fills(df)
    assert len(valid) == 0
    assert len(invalid) == 1
