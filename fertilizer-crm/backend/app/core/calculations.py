from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.crm import Sales, Production, Accounting, Customer

CREDIT_WARN_PCT = Decimal("0.80")   # แจ้งเตือนเมื่อยอดค้างเกิน 80% ของวงเงิน


def check_credit_alert(customer: Customer, new_order_amount) -> bool:
    """คืน True ถ้ายอดค้างชำระ + Order ใหม่ >= 80% ของวงเงิน"""
    if customer.credit_limit <= 0:
        return False
    projected = (customer.outstanding_balance or Decimal("0")) + Decimal(str(new_order_amount))
    return projected >= customer.credit_limit * CREDIT_WARN_PCT


def recalc_accounting(db: Session, order_id: str) -> Accounting:
    """คำนวณ gross_profit และ gross_margin_pct ใหม่จาก production + sales"""
    sales = db.get(Sales, order_id)
    production = db.get(Production, order_id)
    acc = db.get(Accounting, order_id)

    if acc is None:
        acc = Accounting(order_id=order_id)
        db.add(acc)

    total_sales = sales.total_amount or Decimal("0")
    prod_cost = production.production_cost_total if production else Decimal("0")

    acc.total_sales_amount = total_sales
    acc.total_cost_amount = prod_cost or Decimal("0")
    acc.gross_profit = total_sales - acc.total_cost_amount
    acc.gross_margin_pct = (
        round(acc.gross_profit / total_sales * 100, 2) if total_sales else Decimal("0")
    )

    db.commit()
    db.refresh(acc)
    return acc


def deduct_stock_for_order(db: Session, order_id: str) -> list[dict]:
    """
    หักสต็อกวัตถุดิบตาม bom_actual ที่ทีมผลิตยืนยันไว้
    คืน list ของวัตถุดิบที่ต่ำกว่า minimum_qty (สำหรับแจ้งเตือน)
    """
    from app.models.crm import Production, RawMaterial
    import json

    production = db.get(Production, order_id)
    if not production or not production.bom_actual:
        return []

    bom = production.bom_actual  # JSONB — list of {material_name, qty_used}
    alerts = []

    for item in bom:
        mat = db.query(RawMaterial).filter_by(material_name=item["material_name"]).first()
        if mat:
            mat.stock_qty = max(Decimal("0"), mat.stock_qty - Decimal(str(item["qty_used"])))
            if mat.stock_qty < mat.minimum_qty:
                alerts.append({"material_name": mat.material_name, "stock_qty": float(mat.stock_qty), "minimum_qty": float(mat.minimum_qty)})

    db.commit()
    return alerts
