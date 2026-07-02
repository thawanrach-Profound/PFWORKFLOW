import io
import pandas as pd
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])

DASHBOARD_SQL = text("SELECT * FROM v_order_dashboard ORDER BY order_date DESC")


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    rows = db.execute(DASHBOARD_SQL).mappings().all()
    return [dict(r) for r in rows]


@router.get("/dashboard/export")
def export_dashboard(format: str = "csv", db: Session = Depends(get_db)):
    """
    Export สำหรับ Sale Support:
    - format=csv  → นำเข้า Express ได้เลย
    - format=excel → ส่ง Claude วิเคราะห์สูตรปุ๋ย/Forecast
    """
    rows = db.execute(DASHBOARD_SQL).mappings().all()
    df = pd.DataFrame([dict(r) for r in rows])
    buf = io.BytesIO()
    if format == "excel":
        df.to_excel(buf, index=False, sheet_name="Orders")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        fname = "orders.xlsx"
    else:
        df.to_csv(buf, index=False, encoding="utf-8-sig")  # utf-8-sig รองรับภาษาไทยใน Excel
        media = "text/csv"
        fname = "orders.csv"
    buf.seek(0)
    return StreamingResponse(buf, media_type=media,
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """ตัวเลขสรุปสำหรับ KPI Cards บน Dashboard"""
    from sqlalchemy import func as sqlfunc
    from app.models.crm import Sales, Accounting, Production

    total_orders   = db.query(Sales).count()
    pending        = db.query(Sales).filter(Sales.order_status == "PENDING_APPROVAL").count()
    credit_alerts  = db.query(Sales).filter(Sales.credit_alert == True, Sales.order_status.in_(["PENDING_APPROVAL","APPROVED"])).count()
    total_revenue  = db.query(sqlfunc.coalesce(sqlfunc.sum(Accounting.total_sales_amount), 0)).scalar()
    total_profit   = db.query(sqlfunc.coalesce(sqlfunc.sum(Accounting.gross_profit), 0)).scalar()
    waiting_prod   = db.query(Production).filter(Production.production_status == "WAITING").count()
    in_progress    = db.query(Production).filter(Production.production_status == "IN_PROGRESS").count()
    return {
        "total_orders":   total_orders,
        "pending_approval": pending,
        "credit_alerts":  credit_alerts,
        "total_revenue":  float(total_revenue),
        "total_profit":   float(total_profit),
        "waiting_production": waiting_prod,
        "in_production":  in_progress,
    }
