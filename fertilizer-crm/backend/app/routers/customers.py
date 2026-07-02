from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crm import Customer
from app.schemas.crm import CustomerCreate, CustomerUpdate, CustomerOut

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    if db.query(Customer).filter_by(customer_code=payload.customer_code).first():
        raise HTTPException(400, f"รหัสลูกค้า {payload.customer_code} มีอยู่แล้ว")
    c = Customer(**payload.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return c


@router.get("", response_model=list[CustomerOut])
def list_customers(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(Customer)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.order_by(Customer.company_name).all()


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "ไม่พบลูกค้า")
    return c


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "ไม่พบลูกค้า")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit(); db.refresh(c)
    return c


@router.get("/{customer_id}/credit-check")
def credit_check(customer_id: int, order_amount: float, db: Session = Depends(get_db)):
    """ตรวจสอบวงเงินเครดิตก่อนสร้าง Order"""
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "ไม่พบลูกค้า")
    from decimal import Decimal
    from app.core.calculations import check_credit_alert
    amount = Decimal(str(order_amount))
    projected = (c.outstanding_balance or Decimal("0")) + amount
    return {
        "customer_id": customer_id,
        "company_name": c.company_name,
        "credit_limit": float(c.credit_limit),
        "outstanding_balance": float(c.outstanding_balance),
        "order_amount": float(amount),
        "projected_balance": float(projected),
        "credit_alert": check_credit_alert(c, amount),
        "credit_exceeded": projected >= c.credit_limit,
        "credit_remaining": float(c.credit_limit - c.outstanding_balance),
        "credit_term_days": c.credit_term.value,
    }
