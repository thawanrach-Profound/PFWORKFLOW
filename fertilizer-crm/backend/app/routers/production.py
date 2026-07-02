from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.calculations import recalc_accounting, deduct_stock_for_order
from app.models.crm import Production, Sales
from app.schemas.crm import ProductionUpdate, ProductionOut

router = APIRouter(prefix="/api/production", tags=["production"])


@router.get("", response_model=list[ProductionOut])
def list_production(status: str = None, db: Session = Depends(get_db)):
    q = db.query(Production).order_by(Production.created_at.desc())
    if status:
        q = q.filter(Production.production_status == status)
    return q.all()


@router.get("/{order_id}", response_model=ProductionOut)
def get_production(order_id: str, db: Session = Depends(get_db)):
    p = db.get(Production, order_id)
    if not p:
        raise HTTPException(404, "ไม่พบข้อมูลการผลิต")
    return p


@router.put("/{order_id}", response_model=ProductionOut)
def update_production(order_id: str, payload: ProductionUpdate, db: Session = Depends(get_db)):
    p = db.query(Production).filter_by(order_id=order_id).first()
    if not p:
        raise HTTPException(404, "ไม่พบข้อมูลการผลิต")

    prev_status = p.production_status
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit(); db.refresh(p)

    # เมื่อเริ่มผลิต → อัปเดตสถานะ Order
    if payload.production_status == "IN_PROGRESS" and prev_status == "WAITING":
        order = db.get(Sales, order_id)
        if order:
            order.order_status = "IN_PRODUCTION"
            db.commit()

    # เมื่อจัดส่ง → หักสต็อก + คำนวณบัญชี + อัปเดตสถานะ Order
    if payload.production_status == "DISPATCHED":
        stock_alerts = deduct_stock_for_order(db, order_id)
        recalc_accounting(db, order_id)
        order = db.get(Sales, order_id)
        if order:
            order.order_status = "READY_TO_SHIP"
            db.commit()
        if stock_alerts:
            db.refresh(p)
            return {"data": p, "stock_alerts": stock_alerts}

    if payload.raw_material_cost is not None or payload.labor_cost is not None or payload.packaging_cost is not None:
        recalc_accounting(db, order_id)

    db.refresh(p)
    return p
