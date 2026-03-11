"""TCBS XLSX upload and import API."""

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.main import get_database_session
from app.models import TradeFill, Trade, ImportBatch
from app.pipeline.parser import parse_tcbs_xlsx, extract_account_type
from app.pipeline.cleaner import clean_fills, validate_fills
from app.engine.portfolio import calculate_holdings, update_holdings_table

router = APIRouter(tags=["upload"])


@router.post("/api/upload")
async def upload_trades(
    file: UploadFile = File(...),
    session: Session = Depends(get_database_session),
):
    """Upload a TCBS trade history XLSX file."""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "File must be .xlsx or .xls")

    contents = await file.read()
    file_io = BytesIO(contents)

    # Extract account type
    account_type = extract_account_type(file_io)

    # Parse and clean
    file_io.seek(0)
    raw_dataframe = parse_tcbs_xlsx(file_io)
    cleaned_dataframe = clean_fills(raw_dataframe)
    valid_dataframe, invalid_dataframe = validate_fills(cleaned_dataframe)

    if len(valid_dataframe) == 0:
        # Include diagnostic info to help debug column/header issues
        diagnostics = {
            "raw_columns": list(raw_dataframe.columns),
            "raw_row_count": len(raw_dataframe),
            "cleaned_columns": list(cleaned_dataframe.columns),
            "first_raw_row": (
                raw_dataframe.head(1).to_dict(orient="records")[0]
                if not raw_dataframe.empty
                else None
            ),
        }
        raise HTTPException(
            400,
            {
                "message": f"No valid trades found. {len(invalid_dataframe)} rows rejected.",
                "diagnostics": diagnostics,
            },
        )

    # Create import batch
    batch = ImportBatch(
        filename=file.filename,
        account_type=account_type,
        row_count=len(valid_dataframe),
        date_range_start=(
            valid_dataframe["trading_date"].min()
            if "trading_date" in valid_dataframe
            else None
        ),
        date_range_end=(
            valid_dataframe["trading_date"].max()
            if "trading_date" in valid_dataframe
            else None
        ),
    )
    session.add(batch)
    session.flush()

    # Insert fills — check existing DB rows to avoid re-importing
    imported_count = 0
    skipped_count = 0

    # Pre-load existing fill keys for fast lookup
    existing_fills = session.query(
        TradeFill.order_no, TradeFill.matched_price,
        TradeFill.matched_volume, TradeFill.trading_date,
    ).all()
    existing_keys = set(
        (str(f.order_no), float(f.matched_price), int(f.matched_volume), str(f.trading_date))
        for f in existing_fills
    )
    # Track how many times each key appears in DB vs file
    from collections import Counter
    existing_counts = Counter(existing_keys)
    file_key_counts = Counter()

    for _, row in valid_dataframe.iterrows():
        order_no = str(row.get("order_no", ""))
        matched_price = float(row["matched_price"])
        matched_volume = int(row["matched_volume"])
        trading_date = row["trading_date"]

        fill_key = (order_no, matched_price, matched_volume, str(trading_date))
        file_key_counts[fill_key] += 1

        # Skip if this occurrence already exists in DB
        if file_key_counts[fill_key] <= existing_counts.get(fill_key, 0):
            skipped_count += 1
            continue

        fill = TradeFill(
            order_no=order_no,
            ticker=str(row["ticker"]),
            trading_date=trading_date,
            trade_side=str(row["trade_side"]),
            order_volume=int(row.get("order_volume", 0)),
            order_price=float(row.get("order_price", 0)),
            matched_volume=matched_volume,
            matched_price=matched_price,
            matched_value=float(row["matched_value"]),
            fee=float(row.get("fee", 0)),
            tax=float(row.get("tax", 0)),
            cost_basis=(
                float(row.get("cost_basis", 0))
                if row.get("cost_basis")
                else None
            ),
            return_pnl=float(row.get("return_pnl", 0)),
            channel=(
                str(row.get("channel", ""))
                if row.get("channel")
                else None
            ),
            status=(
                str(row.get("status", ""))
                if row.get("status")
                else None
            ),
            order_type=(
                str(row.get("order_type", ""))
                if row.get("order_type")
                else None
            ),
            account_type=account_type,
            import_batch_id=batch.id,
        )
        session.add(fill)
        session.flush()
        imported_count += 1

    # Aggregate fills into trades
    _aggregate_trades(session, valid_dataframe, account_type)

    # Update holdings
    holdings = calculate_holdings(session)
    update_holdings_table(session, holdings)

    session.commit()

    return {
        "fills_imported": imported_count,
        "fills_skipped": skipped_count,
        "invalid_rows": len(invalid_dataframe),
        "account_type": account_type,
        "batch_id": batch.id,
    }


def _aggregate_trades(
    session: Session, fills_dataframe, account_type: str
):
    """Aggregate fills with same order_no into Trade records."""
    if "order_no" not in fills_dataframe.columns:
        return

    for order_no, group in fills_dataframe.groupby("order_no"):
        existing = (
            session.query(Trade).filter_by(order_no=str(order_no)).first()
        )
        if existing:
            continue

        total_volume = int(group["matched_volume"].sum())
        total_value = float(group["matched_value"].sum())

        trade = Trade(
            order_no=str(order_no),
            ticker=str(group.iloc[0]["ticker"]),
            trading_date=group.iloc[0]["trading_date"],
            trade_side=str(group.iloc[0]["trade_side"]),
            total_matched_volume=total_volume,
            vwap_matched_price=(
                total_value / total_volume if total_volume > 0 else 0
            ),
            total_matched_value=total_value,
            total_fee=float(group["fee"].sum()),
            total_tax=float(group["tax"].sum()),
            total_return_pnl=float(group["return_pnl"].sum()),
            account_type=account_type,
            order_type=(
                str(group.iloc[0].get("order_type", ""))
                if group.iloc[0].get("order_type")
                else None
            ),
        )
        session.add(trade)

    session.flush()
