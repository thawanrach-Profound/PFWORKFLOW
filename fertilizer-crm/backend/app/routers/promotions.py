from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crm import Promotion, PromotionGift, OrderPromotion, GiftDispatch, Sales
from app.schemas.crm import (
    PromotionCreate, PromotionUpdate, PromotionOut,
    PromotionGiftCreate, PromotionGiftOut, PromotionGiftStockUpdate,
    OrderPromotionIn, OrderPromotionOut,
    GiftDispatchCreate, GiftDispatchOut,
)

router = APIRouter(prefix="/api/promotions", tags=["promotions"])


# ── Promotions CRUD ───────────────────────────────────────────

@router.get("", response_model=list[PromotionOut])
def list_promotions(active_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(Promotion).order_by(Promotion.created_at.desc())
    if active_only:
        q = q.filter(Promotion.is_active == True)
    return q.all()


@router.post("", response_model=PromotionOut, status_code=201)
def create_promotion(payload: PromotionCreate, db: Session = Depends(get_db)):
    promo = Promotion(
        promo_name=payload.promo_name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
        notes=payload.notes,
    )
    db.add(promo); db.flush()
    for g in payload.gifts:
        db.add(PromotionGift(
            promotion_id=promo.promotion_id,
            gift_name=g.gift_name,
            unit=g.unit,
            stock_qty=g.stock_qty,
            notes=g.notes,
        ))
    db.commit(); db.refresh(promo)
    return promo


@router.get("/{promo_id}", response_model=PromotionOut)
def get_promotion(promo_id: int, db: Session = Depends(get_db)):
    p = db.get(Promotion, promo_id)
    if not p:
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")
    return p


@router.put("/{promo_id}", response_model=PromotionOut)
def update_promotion(promo_id: int, payload: PromotionUpdate, db: Session = Depends(get_db)):
    p = db.get(Promotion, promo_id)
    if not p:
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")
    data = payload.model_dump(exclude_unset=True)
    gifts_payload = data.pop("gifts", None)
    for k, v in data.items():
        setattr(p, k, v)
    if gifts_payload is not None:
        for g in list(p.gifts):
            db.delete(g)
        db.flush()
        for g in gifts_payload:
            db.add(PromotionGift(promotion_id=promo_id, **g))
    db.commit(); db.refresh(p)
    return p


@router.delete("/{promo_id}", status_code=204)
def delete_promotion(promo_id: int, db: Session = Depends(get_db)):
    p = db.get(Promotion, promo_id)
    if not p:
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")
    db.delete(p); db.commit()


# ── Gifts CRUD ────────────────────────────────────────────────

@router.post("/{promo_id}/gifts", response_model=PromotionGiftOut, status_code=201)
def add_gift(promo_id: int, payload: PromotionGiftCreate, db: Session = Depends(get_db)):
    if not db.get(Promotion, promo_id):
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")
    g = PromotionGift(promotion_id=promo_id, **payload.model_dump())
    db.add(g); db.commit(); db.refresh(g)
    return g


@router.put("/{promo_id}/gifts/{gift_id}", response_model=PromotionGiftOut)
def update_gift(promo_id: int, gift_id: int, payload: PromotionGiftCreate, db: Session = Depends(get_db)):
    g = db.get(PromotionGift, gift_id)
    if not g or g.promotion_id != promo_id:
        raise HTTPException(404, "ไม่พบของแจก")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    db.commit(); db.refresh(g)
    return g


@router.patch("/{promo_id}/gifts/{gift_id}/stock", response_model=PromotionGiftOut)
def set_gift_stock(promo_id: int, gift_id: int, payload: PromotionGiftStockUpdate, db: Session = Depends(get_db)):
    g = db.get(PromotionGift, gift_id)
    if not g or g.promotion_id != promo_id:
        raise HTTPException(404, "ไม่พบของแจก")
    g.stock_qty = payload.stock_qty
    db.commit(); db.refresh(g)
    return g


@router.delete("/{promo_id}/gifts/{gift_id}", status_code=204)
def delete_gift(promo_id: int, gift_id: int, db: Session = Depends(get_db)):
    g = db.get(PromotionGift, gift_id)
    if not g or g.promotion_id != promo_id:
        raise HTTPException(404, "ไม่พบของแจก")
    db.delete(g); db.commit()


# ── Order Promotions ──────────────────────────────────────────

@router.get("/order/{order_id}", response_model=list[OrderPromotionOut])
def list_order_promotions(order_id: str, db: Session = Depends(get_db)):
    return db.query(OrderPromotion).filter(OrderPromotion.order_id == order_id).all()


@router.post("/order/{order_id}", response_model=OrderPromotionOut, status_code=201)
def add_order_promotion(order_id: str, payload: OrderPromotionIn, db: Session = Depends(get_db)):
    """บันทึกว่า Order นี้ใช้โปรโมชันใด — ยังไม่ตัด stock (ตัดเมื่อแจกจริงผ่าน dispatch)"""
    order = db.get(Sales, order_id)
    if not order:
        raise HTTPException(404, f"ไม่พบ Order {order_id}")
    gift = db.get(PromotionGift, payload.gift_id)
    if not gift or gift.promotion_id != payload.promotion_id:
        raise HTTPException(404, "ไม่พบของแจก")

    op = OrderPromotion(
        order_id=order_id,
        promotion_id=payload.promotion_id,
        gift_id=payload.gift_id,
        gift_name=gift.gift_name,
        qty_given=payload.qty_given,
        unit=gift.unit,
        notes=payload.notes,
    )
    db.add(op); db.commit(); db.refresh(op)
    return op


@router.delete("/order/{order_id}/{op_id}", status_code=204)
def remove_order_promotion(order_id: str, op_id: int, db: Session = Depends(get_db)):
    op = db.get(OrderPromotion, op_id)
    if not op or op.order_id != order_id:
        raise HTTPException(404, "ไม่พบรายการ")
    db.delete(op); db.commit()


# ── Gift Dispatches (บันทึกการแจกจริงแต่ละครั้ง) ─────────────

@router.get("/order/{order_id}/{op_id}/dispatches", response_model=list[GiftDispatchOut])
def list_dispatches(order_id: str, op_id: int, db: Session = Depends(get_db)):
    op = db.get(OrderPromotion, op_id)
    if not op or op.order_id != order_id:
        raise HTTPException(404, "ไม่พบรายการ")
    return db.query(GiftDispatch).filter(GiftDispatch.op_id == op_id).order_by(GiftDispatch.dispatch_date).all()


@router.post("/order/{order_id}/{op_id}/dispatches", response_model=GiftDispatchOut, status_code=201)
def add_dispatch(order_id: str, op_id: int, payload: GiftDispatchCreate, db: Session = Depends(get_db)):
    """บันทึกการแจกของจริง — ตัด stock ณ เวลานี้"""
    op = db.get(OrderPromotion, op_id)
    if not op or op.order_id != order_id:
        raise HTTPException(404, "ไม่พบรายการโปรโมชันใน Order")

    # ตรวจสอบว่าแจกไม่เกินจำนวนที่วางแผน
    already = sum(d.qty_dispatched for d in op.dispatches)
    remaining_plan = op.qty_given - already
    if payload.qty_dispatched > remaining_plan:
        raise HTTPException(400, f"แจกเกินจำนวนที่วางแผน (วางแผน {op.qty_given}, แจกไปแล้ว {already}, คงเหลือ {remaining_plan} {op.unit})")

    # ตัด stock
    gift = db.get(PromotionGift, op.gift_id)
    if gift:
        if gift.stock_qty < payload.qty_dispatched:
            raise HTTPException(400, f"Stock ของแจก '{gift.gift_name}' ไม่พอ (คงเหลือ {gift.stock_qty} {gift.unit})")
        gift.stock_qty -= payload.qty_dispatched

    d = GiftDispatch(
        op_id=op_id,
        dispatch_date=payload.dispatch_date,
        qty_dispatched=payload.qty_dispatched,
        dispatched_by=payload.dispatched_by,
        shop_name=payload.shop_name,
        region=payload.region,
        notes=payload.notes,
    )
    db.add(d); db.commit(); db.refresh(d)
    return d


@router.delete("/order/{order_id}/{op_id}/dispatches/{dispatch_id}", status_code=204)
def delete_dispatch(order_id: str, op_id: int, dispatch_id: int, db: Session = Depends(get_db)):
    """ลบบันทึกการแจก — คืน stock"""
    d = db.get(GiftDispatch, dispatch_id)
    if not d or d.op_id != op_id:
        raise HTTPException(404, "ไม่พบบันทึกการแจก")
    # คืน stock
    op = db.get(OrderPromotion, op_id)
    if op:
        gift = db.get(PromotionGift, op.gift_id)
        if gift:
            gift.stock_qty += d.qty_dispatched
    db.delete(d); db.commit()


@router.get("/dispatches/summary", response_model=list[dict])
def dispatch_summary(db: Session = Depends(get_db)):
    """สรุปการแจกของแจกทั้งหมด — ใช้แสดงในเมนูวิธีการตัดของแจก"""
    from sqlalchemy import func as sqlfunc
    rows = (
        db.query(
            OrderPromotion.op_id,
            OrderPromotion.order_id,
            OrderPromotion.gift_name,
            OrderPromotion.qty_given,
            OrderPromotion.unit,
            sqlfunc.coalesce(sqlfunc.sum(GiftDispatch.qty_dispatched), 0).label("qty_dispatched"),
        )
        .outerjoin(GiftDispatch, GiftDispatch.op_id == OrderPromotion.op_id)
        .group_by(OrderPromotion.op_id, OrderPromotion.order_id, OrderPromotion.gift_name, OrderPromotion.qty_given, OrderPromotion.unit)
        .order_by(OrderPromotion.op_id.desc())
        .all()
    )
    return [
        {
            "op_id": r.op_id,
            "order_id": r.order_id,
            "gift_name": r.gift_name,
            "qty_given": float(r.qty_given),
            "qty_dispatched": float(r.qty_dispatched),
            "qty_remaining": float(r.qty_given) - float(r.qty_dispatched),
            "unit": r.unit,
        }
        for r in rows
    ]


@router.get("/dispatches/region-summary", response_model=list[dict])
def region_summary(db: Session = Depends(get_db)):
    """สรุปการแจกของแจกแยกตามภาค x ประเภทของแจก"""
    from sqlalchemy import func as sqlfunc
    rows = (
        db.query(
            sqlfunc.coalesce(GiftDispatch.region, "ไม่ระบุ").label("region"),
            OrderPromotion.gift_name,
            sqlfunc.sum(GiftDispatch.qty_dispatched).label("total_qty"),
        )
        .join(OrderPromotion, GiftDispatch.op_id == OrderPromotion.op_id)
        .group_by(GiftDispatch.region, OrderPromotion.gift_name)
        .order_by("region", OrderPromotion.gift_name)
        .all()
    )
    return [{"region": r.region, "gift_name": r.gift_name, "total_qty": float(r.total_qty)} for r in rows]


@router.get("/dispatches/shop-summary", response_model=list[dict])
def shop_summary(db: Session = Depends(get_db)):
    """สรุปการแจกของแจกแยกตามร้านค้า"""
    from sqlalchemy import func as sqlfunc
    rows = (
        db.query(
            sqlfunc.coalesce(GiftDispatch.shop_name, "ไม่ระบุร้าน").label("shop_name"),
            sqlfunc.coalesce(GiftDispatch.region, "ไม่ระบุ").label("region"),
            OrderPromotion.gift_name,
            sqlfunc.sum(GiftDispatch.qty_dispatched).label("total_qty"),
        )
        .join(OrderPromotion, GiftDispatch.op_id == OrderPromotion.op_id)
        .group_by(GiftDispatch.shop_name, GiftDispatch.region, OrderPromotion.gift_name)
        .order_by("region", "shop_name")
        .all()
    )
    return [{"shop_name": r.shop_name, "region": r.region, "gift_name": r.gift_name, "total_qty": float(r.total_qty)} for r in rows]
