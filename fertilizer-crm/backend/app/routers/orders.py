from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.calculations import check_credit_alert
from app.models.crm import Sales, Customer, OrderItem, Production, Accounting
from app.schemas.crm import OrderCreate, OrderApprove, OrderReject, OrderOut, OrderItemIn, OrderItemOut

router = APIRouter(prefix="/api/orders", tags=["orders"])

# สถานะที่ยังแก้ไขข้อมูลได้
EDITABLE_STATUSES = {"DRAFT", "EDIT"}
# สถานะที่ยังยกเลิกได้
CANCELLABLE_STATUSES = {"DRAFT", "EDIT", "PENDING_APPROVAL", "APPROVED", "REJECTED"}


class OrderEditPayload(BaseModel):
    salesperson: Optional[str] = None
    sale_support_name: Optional[str] = None
    dept: Optional[str] = None
    delivery_due_date: Optional[str] = None
    line_note: Optional[str] = None
    notes: Optional[str] = None


def _get_order_or_404(order_id: str, db: Session) -> Sales:
    o = db.get(Sales, order_id)
    if not o:
        raise HTTPException(404, f"ไม่พบ Order {order_id}")
    return o


def _recalc_total(order: Sales) -> None:
    order.total_amount = sum(i.line_amount or 0 for i in order.items)


@router.post("", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    if db.get(Sales, payload.order_id):
        raise HTTPException(400, f"Order ID {payload.order_id} ซ้ำ")

    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(404, "ไม่พบลูกค้า")

    initial = payload.initial_status or "DRAFT"
    if initial not in ("DRAFT", "PENDING_APPROVAL"):
        initial = "DRAFT"

    order = Sales(
        order_id=payload.order_id,
        customer_id=payload.customer_id,
        salesperson=payload.salesperson,
        sale_support_name=payload.sale_support_name,
        dept=payload.dept,
        order_status=initial,
        credit_limit_snapshot=customer.credit_limit,
        outstanding_snapshot=customer.outstanding_balance,
        delivery_due_date=payload.delivery_due_date,
        line_note=payload.line_note,
        notes=payload.notes,
    )
    db.add(order); db.flush()

    for i, item in enumerate(payload.items, 1):
        db.add(OrderItem(
            order_id=order.order_id,
            seq=item.seq or i,
            product_code=item.product_code,
            product_name=item.product_name,
            quantity_ton=item.quantity_ton,
            unit=item.unit,
            unit_price=item.unit_price,
            discount=item.discount,
            so_ref=item.so_ref,
            notes=item.notes,
        ))
    db.flush()
    db.refresh(order)
    _recalc_total(order)

    order.credit_alert = check_credit_alert(customer, float(order.total_amount or 0))
    db.add(Production(order_id=order.order_id))
    db.add(Accounting(order_id=order.order_id, total_sales_amount=order.total_amount or 0))
    db.commit(); db.refresh(order)
    return order


@router.get("", response_model=list[OrderOut])
def list_orders(status: str = None, db: Session = Depends(get_db)):
    q = db.query(Sales).order_by(Sales.order_date.desc())
    if status:
        q = q.filter(Sales.order_status == status)
    return q.all()


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db)):
    return _get_order_or_404(order_id, db)


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_order(order_id: str, db: Session = Depends(get_db)):
    """Draft → Confirm (PENDING_APPROVAL) — Sale Support กด Confirm เพื่อส่งอนุมัติ"""
    order = _get_order_or_404(order_id, db)
    if order.order_status not in EDITABLE_STATUSES:
        raise HTTPException(400, f"ไม่สามารถ Confirm Order ที่อยู่ในสถานะ {order.order_status}")
    order.order_status = "PENDING_APPROVAL"
    db.commit(); db.refresh(order)
    return order


@router.post("/{order_id}/send-edit", response_model=OrderOut)
def send_back_to_edit(order_id: str, reason: str = "ขอแก้ไขข้อมูล", db: Session = Depends(get_db)):
    """ส่งกลับให้แก้ไข (EDIT) — Sale Support หรือ Approver ส่งกลับ"""
    order = _get_order_or_404(order_id, db)
    if order.order_status in ("DELIVERED", "CANCELLED", "IN_PRODUCTION"):
        raise HTTPException(400, f"ไม่สามารถส่งกลับแก้ไข Order ที่อยู่ในสถานะ {order.order_status}")
    order.order_status = "EDIT"
    order.rejected_reason = reason
    db.commit(); db.refresh(order)
    return order


@router.put("/{order_id}/edit", response_model=OrderOut)
def edit_order(order_id: str, payload: OrderEditPayload, db: Session = Depends(get_db)):
    """แก้ไขข้อมูล Order — ทำได้เฉพาะสถานะ DRAFT หรือ EDIT"""
    order = _get_order_or_404(order_id, db)
    if order.order_status not in EDITABLE_STATUSES:
        raise HTTPException(400, f"ไม่สามารถแก้ไข Order ที่อยู่ในสถานะ {order.order_status} (แก้ไขได้เฉพาะ Draft/Edit)")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(order, field, value)
    db.commit(); db.refresh(order)
    return order


@router.post("/{order_id}/approve", response_model=OrderOut)
def approve_order(order_id: str, payload: OrderApprove, db: Session = Depends(get_db)):
    order = _get_order_or_404(order_id, db)
    if order.order_status != "PENDING_APPROVAL":
        raise HTTPException(400, "Order ต้องอยู่ในสถานะ PENDING_APPROVAL (Confirm)")
    order.order_status = "APPROVED"
    order.approved_by = payload.approved_by
    order.approved_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(order)
    return order


@router.post("/{order_id}/reject", response_model=OrderOut)
def reject_order(order_id: str, payload: OrderReject, db: Session = Depends(get_db)):
    order = _get_order_or_404(order_id, db)
    if order.order_status not in ("PENDING_APPROVAL",):
        raise HTTPException(400, "ไม่สามารถ Reject Order ในสถานะนี้ได้")
    order.order_status = "REJECTED"
    order.rejected_reason = payload.rejected_reason
    db.commit(); db.refresh(order)
    return order


@router.delete("/{order_id}", status_code=204)
def cancel_order(order_id: str, db: Session = Depends(get_db)):
    order = _get_order_or_404(order_id, db)
    if order.order_status not in CANCELLABLE_STATUSES:
        raise HTTPException(400, "ไม่สามารถยกเลิก Order ในสถานะนี้ได้")
    order.order_status = "CANCELLED"
    db.commit()


# ── Order Items ───────────────────────────────────────────────
@router.get("/{order_id}/items", response_model=list[OrderItemOut])
def list_items(order_id: str, db: Session = Depends(get_db)):
    _get_order_or_404(order_id, db)
    return db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.seq).all()


@router.post("/{order_id}/items", response_model=OrderItemOut, status_code=201)
def add_item(order_id: str, payload: OrderItemIn, db: Session = Depends(get_db)):
    order = _get_order_or_404(order_id, db)
    if order.order_status not in EDITABLE_STATUSES:
        raise HTTPException(400, "แก้ไขได้เฉพาะ Draft/Edit")
    item = OrderItem(order_id=order_id, **payload.model_dump())
    db.add(item); db.flush()
    db.refresh(order)
    _recalc_total(order)
    acc = db.get(Accounting, order_id)
    if acc: acc.total_sales_amount = order.total_amount
    db.commit(); db.refresh(item)
    return item


@router.put("/{order_id}/items/{item_id}", response_model=OrderItemOut)
def update_item(order_id: str, item_id: int, payload: OrderItemIn, db: Session = Depends(get_db)):
    order = _get_order_or_404(order_id, db)
    if order.order_status not in EDITABLE_STATUSES:
        raise HTTPException(400, "แก้ไขได้เฉพาะ Draft/Edit")
    item = db.get(OrderItem, item_id)
    if not item or item.order_id != order_id:
        raise HTTPException(404, "ไม่พบรายการสินค้า")
    for k, v in payload.model_dump().items():
        setattr(item, k, v)
    db.flush()
    db.refresh(order)
    _recalc_total(order)
    acc = db.get(Accounting, order_id)
    if acc: acc.total_sales_amount = order.total_amount
    db.commit(); db.refresh(item)
    return item


@router.delete("/{order_id}/items/{item_id}", status_code=204)
def delete_item(order_id: str, item_id: int, db: Session = Depends(get_db)):
    order = _get_order_or_404(order_id, db)
    if order.order_status not in EDITABLE_STATUSES:
        raise HTTPException(400, "แก้ไขได้เฉพาะ Draft/Edit")
    item = db.get(OrderItem, item_id)
    if not item or item.order_id != order_id:
        raise HTTPException(404, "ไม่พบรายการสินค้า")
    db.delete(item); db.flush()
    db.refresh(order)
    _recalc_total(order)
    acc = db.get(Accounting, order_id)
    if acc: acc.total_sales_amount = order.total_amount
    db.commit()
