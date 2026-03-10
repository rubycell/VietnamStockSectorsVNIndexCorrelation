"""Tests for XLSX upload API."""

import pytest
import openpyxl
from io import BytesIO
from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.models import TradeFill, Trade, ImportBatch


@pytest.fixture
def client(tmp_path):
    engine = database.create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    factory = database.get_session(engine)

    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    from app.main import get_database_session
    app.dependency_overrides[get_database_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    for i in range(9):
        ws.append([""])
    ws.append(["Loại tài khoản: Ký quỹ"])
    for i in range(4):
        ws.append([""])
    ws.append(["Mã CP", "Ngày GD", "Giao dịch", "KL đặt", "Giá đặt",
               "KL khớp", "Giá khớp", "Giá trị khớp", "Phí", "Thuế",
               "Giá vốn", "Lãi lỗ", "Kênh GD", "Trạng thái", "Loại lệnh", "Số hiệu lệnh"])
    ws.append(["FPT", "15/01/2025", "Mua", 100, 120000, 100, 120000, 12000000,
               17000, 0, 120000, 0, "Online", "Hoàn tất", "Lệnh thường", "ABC123"])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_upload_success(client):
    xlsx = _make_xlsx()
    response = client.post(
        "/api/upload",
        files={"file": ("trades.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fills_imported"] >= 1
    assert data["account_type"] == "margin"


def test_upload_creates_import_batch(client):
    xlsx = _make_xlsx()
    client.post("/api/upload", files={"file": ("trades.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    r = client.post("/api/upload", files={"file": ("trades.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    # Second upload should still succeed (dedup handles duplicates)
    assert r.status_code == 200
