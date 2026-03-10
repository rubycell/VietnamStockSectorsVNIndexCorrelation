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
        raise HTTPException(
            400,
            f"No valid trades found. {len(invalid_dataframe)} rows rejected.",
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

    # Insert fills with deduplication via savepoints
    imported_count = 0
    skipped_count = 0

    for _, row in valid_dataframe.iterrows():
        fill = TradeFill(
            order_no=str(row.get("order_no", "")),
            ticker=str(row["ticker"]),
            trading_date=row["trading_date"],
            trade_side=str(row["trade_side"]),
            order_volume=int(row.get("order_volume", 0)),
            order_price=float(row.get("order_price", 0)),
            matched_volume=int(row["matched_volume"]),
            matched_price=float(row["matched_price"]),
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
        savepoint = session.begin_nested()
        try:
            session.add(fill)
            session.flush()
            imported_count += 1
        except IntegrityError:
            savepoint.rollback()
            skipped_count += 1

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
