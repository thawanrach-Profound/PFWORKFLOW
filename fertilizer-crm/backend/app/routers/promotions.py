from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.models.crm import Promotion, PromotionGift, PromoShop, OrderPromotion, GiftDispatch, Sales, Customer, OrderItem
from app.schemas.crm import (
    PromotionCreate, PromotionUpdate, PromotionOut,
    PromotionGiftCreate, PromotionGiftOut, PromotionGiftStockUpdate,
    PromoShopCreate, PromoShopOut,
    OrderPromotionIn, OrderPromotionOut,
    GiftDispatchCreate, DirectDispatchCreate, GiftDispatchOut,
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
        product_filter=payload.product_filter,
        multiplier=payload.multiplier,
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
            qty_per_ton=g.qty_per_ton,
            notes=g.notes,
        ))
    for s in payload.shops:
        db.add(PromoShop(
            promotion_id=promo.promotion_id,
            shop_name=s.shop_name,
            region=s.region,
            qty_ton=s.qty_ton,
            qty_allocated=s.qty_allocated,
            notes=s.notes,
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
    shops_payload = data.pop("shops", None)
    for k, v in data.items():
        setattr(p, k, v)
    if gifts_payload is not None:
        # upsert ตามชื่อของแจก — คง gift_id เดิมไว้เพื่อไม่ให้ FK จาก order/dispatch พัง
        existing = {g.gift_name: g for g in p.gifts}
        payload_names = set()
        for g in gifts_payload:
            payload_names.add(g["gift_name"])
            if g["gift_name"] in existing:
                for k, v in g.items():
                    setattr(existing[g["gift_name"]], k, v)
            else:
                db.add(PromotionGift(promotion_id=promo_id, **g))
        for name, gift in existing.items():
            if name not in payload_names:
                used = db.query(OrderPromotion).filter(OrderPromotion.gift_id == gift.gift_id).count()
                if used:
                    raise HTTPException(400, f"ลบของแจก '{name}' ไม่ได้ — มี order ใช้อยู่ {used} รายการ")
                db.query(GiftDispatch).filter(GiftDispatch.gift_id == gift.gift_id)\
                    .update({"gift_id": None}, synchronize_session=False)
                db.delete(gift)
    if shops_payload is not None:
        # upsert ตามชื่อร้าน — คง shop_id และ qty_dispatched เดิมไว้
        existing_shops = {s.shop_name: s for s in p.shops}
        payload_shop_names = set()
        for s in shops_payload:
            payload_shop_names.add(s["shop_name"])
            if s["shop_name"] in existing_shops:
                cur = existing_shops[s["shop_name"]]
                for k, v in s.items():
                    if k != "qty_dispatched":
                        setattr(cur, k, v)
            else:
                db.add(PromoShop(promotion_id=promo_id, **s))
        for name, shop in existing_shops.items():
            if name not in payload_shop_names:
                db.query(GiftDispatch).filter(GiftDispatch.promo_shop_id == shop.shop_id)\
                    .update({"promo_shop_id": None}, synchronize_session=False)
                db.delete(shop)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"บันทึกไม่สำเร็จ: {str(e)[:300]}")
    db.refresh(p)
    return p


@router.delete("/{promo_id}", status_code=204)
def delete_promotion(promo_id: int, db: Session = Depends(get_db)):
    p = db.get(Promotion, promo_id)
    if not p:
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")

    used = db.query(OrderPromotion).filter(OrderPromotion.promotion_id == promo_id).count()
    if used:
        raise HTTPException(400, f"ลบไม่ได้ — มี order ใช้โปรโมชันนี้อยู่ {used} รายการ")

    gift_ids = [g.gift_id for g in p.gifts]
    shop_ids = [s.shop_id for s in p.shops]
    # ปลด FK จากประวัติการแจกก่อนลบ (เก็บประวัติไว้ แต่ตัดลิงก์)
    if gift_ids:
        db.query(GiftDispatch).filter(GiftDispatch.gift_id.in_(gift_ids))\
            .update({"gift_id": None}, synchronize_session=False)
    if shop_ids:
        db.query(GiftDispatch).filter(GiftDispatch.promo_shop_id.in_(shop_ids))\
            .update({"promo_shop_id": None}, synchronize_session=False)

    try:
        db.delete(p)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"ลบไม่สำเร็จ: {str(e)[:300]}")


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
    if payload.stock_qty is not None:
        g.stock_qty = payload.stock_qty
    if payload.dead_stock_qty is not None:
        g.dead_stock_qty = payload.dead_stock_qty
    if payload.gift_image_url is not None:
        g.gift_image_url = payload.gift_image_url or None
    if payload.team is not None:
        g.team = payload.team or None
    # รับเข้าสต๊อก — บวกเพิ่มและบันทึกประวัติ
    if payload.receive_qty and payload.receive_qty > 0:
        g.stock_qty = (g.stock_qty or 0) + payload.receive_qty
        db.add(GiftDispatch(
            op_id=None,
            gift_id=g.gift_id,
            dispatch_date=payload.receive_date or date.today(),
            qty_dispatched=payload.receive_qty,
            dispatch_type="receive",
            dispatched_by=payload.received_by,
            shop_name="รับเข้าสต๊อก",
            notes=f"รับเข้าสต๊อก {payload.receive_qty} {g.unit}" + (f" โดย {payload.received_by}" if payload.received_by else ""),
        ))
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


# ── PromoShops CRUD ───────────────────────────────────────────

@router.get("/{promo_id}/shops", response_model=list[PromoShopOut])
def list_promo_shops(promo_id: int, db: Session = Depends(get_db)):
    if not db.get(Promotion, promo_id):
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")
    return db.query(PromoShop).filter(PromoShop.promotion_id == promo_id).all()


@router.post("/{promo_id}/shops", response_model=PromoShopOut, status_code=201)
def add_promo_shop(promo_id: int, payload: PromoShopCreate, db: Session = Depends(get_db)):
    if not db.get(Promotion, promo_id):
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")
    s = PromoShop(promotion_id=promo_id, **payload.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return s


@router.put("/{promo_id}/shops/{shop_id}", response_model=PromoShopOut)
def update_promo_shop(promo_id: int, shop_id: int, payload: PromoShopCreate, db: Session = Depends(get_db)):
    s = db.get(PromoShop, shop_id)
    if not s or s.promotion_id != promo_id:
        raise HTTPException(404, "ไม่พบร้านค้า")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return s


@router.delete("/{promo_id}/shops/{shop_id}", status_code=204)
def delete_promo_shop(promo_id: int, shop_id: int, db: Session = Depends(get_db)):
    s = db.get(PromoShop, shop_id)
    if not s or s.promotion_id != promo_id:
        raise HTTPException(404, "ไม่พบร้านค้า")
    db.delete(s); db.commit()


# ── Direct Dispatch (แจกตรง promo → shop → gift) ─────────────

@router.post("/dispatches/direct", response_model=GiftDispatchOut, status_code=201)
def direct_dispatch(payload: DirectDispatchCreate, db: Session = Depends(get_db)):
    """แจกของแจกโดยตรง: ตัดสต๊อก — promo_shop_id optional"""
    gift = db.get(PromotionGift, payload.gift_id)
    if not gift:
        raise HTTPException(404, "ไม่พบของแจก")

    # ตรวจ stock ของแจก
    if gift.stock_qty < payload.qty_dispatched:
        raise HTTPException(400, f"Stock ของแจก '{gift.gift_name}' ไม่พอ (คงเหลือ {gift.stock_qty} {gift.unit})")

    shop_name = payload.shop_name
    region = payload.region

    # ถ้ามี promo_shop_id → ตรวจ/ตัดโควต้าร้านด้วย
    if payload.promo_shop_id:
        shop = db.get(PromoShop, payload.promo_shop_id)
        if shop:
            remaining_quota = shop.qty_allocated - shop.qty_dispatched
            if payload.qty_dispatched > remaining_quota:
                raise HTTPException(400, f"แจกเกินสิทธิ์ร้าน (สิทธิ์คงเหลือ {remaining_quota} {gift.unit})")
            shop.qty_dispatched += payload.qty_dispatched
            shop_name = shop_name or shop.shop_name
            region = region or shop.region

    gift.stock_qty -= payload.qty_dispatched

    d = GiftDispatch(
        op_id=None,
        promo_shop_id=payload.promo_shop_id,
        gift_id=payload.gift_id,
        dispatch_date=payload.dispatch_date,
        qty_dispatched=payload.qty_dispatched,
        dispatch_type=payload.dispatch_type,
        dispatched_by=payload.dispatched_by,
        salesperson_name=payload.salesperson_name,
        shop_name=shop_name,
        region=region,
        notes=payload.notes,
    )
    db.add(d); db.commit(); db.refresh(d)
    return d


@router.get("/dispatches/direct", response_model=list[dict])
def list_direct_dispatches(
    promo_id: int = None,
    gift_id: int = None,
    dispatch_type: str = None,
    shop: str = None,
    date_from: date = None,
    date_to: date = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """รายการแจกของแจกโดยตรง (ทั้งผ่าน promo_shop และตรงจากสต๊อก)"""
    q = db.query(GiftDispatch).filter(GiftDispatch.gift_id.isnot(None))
    if promo_id:
        q = q.join(PromoShop, GiftDispatch.promo_shop_id == PromoShop.shop_id)\
             .filter(PromoShop.promotion_id == promo_id)
    if gift_id:
        q = q.filter(GiftDispatch.gift_id == gift_id)
    if dispatch_type:
        q = q.filter(GiftDispatch.dispatch_type == dispatch_type)
    if shop:
        q = q.filter(GiftDispatch.shop_name.ilike(f"%{shop}%"))
    if date_from:
        q = q.filter(GiftDispatch.dispatch_date >= date_from)
    if date_to:
        q = q.filter(GiftDispatch.dispatch_date <= date_to)
    rows = q.order_by(GiftDispatch.dispatch_date.desc(), GiftDispatch.dispatch_id.desc()).limit(limit).all()
    return [
        {
            "dispatch_id": d.dispatch_id,
            "promo_shop_id": d.promo_shop_id,
            "gift_id": d.gift_id,
            "gift_name": d.gift.gift_name if d.gift else "",
            "gift_unit": d.gift.unit if d.gift else "",
            "shop_name": d.shop_name,
            "region": d.region,
            "dispatch_date": str(d.dispatch_date),
            "qty_dispatched": float(d.qty_dispatched),
            "dispatch_type": d.dispatch_type or "dispatch",
            "dispatched_by": d.dispatched_by,
            "salesperson_name": d.salesperson_name,
            "notes": d.notes,
        }
        for d in rows
    ]


@router.delete("/dispatches/direct/{dispatch_id}", status_code=204)
def delete_direct_dispatch(dispatch_id: int, db: Session = Depends(get_db)):
    """ลบบันทึกการแจกตรง — คืน stock และ quota (รายการรับเข้า: หัก stock กลับ)"""
    d = db.get(GiftDispatch, dispatch_id)
    if not d or d.gift_id is None:
        raise HTTPException(404, "ไม่พบบันทึกการแจก")
    if d.gift:
        if d.dispatch_type == "receive":
            d.gift.stock_qty -= d.qty_dispatched
        else:
            d.gift.stock_qty += d.qty_dispatched
    if d.promo_shop and d.dispatch_type != "receive":
        d.promo_shop.qty_dispatched -= d.qty_dispatched
    db.delete(d); db.commit()


@router.get("/{promo_id}/gift-stock", response_model=list[dict])
def get_gift_stock(promo_id: int, db: Session = Depends(get_db)):
    """รายการสต๊อกของแจกในโปรโมชัน"""
    if not db.get(Promotion, promo_id):
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")
    gifts = db.query(PromotionGift).filter(PromotionGift.promotion_id == promo_id).all()
    return [
        {
            "gift_id": g.gift_id,
            "promotion_id": g.promotion_id,
            "gift_name": g.gift_name,
            "unit": g.unit,
            "stock_qty": float(g.stock_qty),
            "qty_per_ton": float(g.qty_per_ton),
            "dead_stock_qty": float(g.dead_stock_qty or 0),
            "gift_image_url": g.gift_image_url,
            "team": g.team,
        }
        for g in gifts
    ]


@router.get("/gifts/all-stock", response_model=list[dict])
def all_gift_stock(db: Session = Depends(get_db)):
    """รายการสต๊อกของแจกทั้งหมดทุกโปรโมชัน"""
    from sqlalchemy.orm import joinedload
    gifts = db.query(PromotionGift).join(Promotion).options(joinedload(PromotionGift.promotion)).all()
    return [
        {
            "gift_id": g.gift_id,
            "promotion_id": g.promotion_id,
            "promo_name": g.promotion.promo_name if g.promotion else "",
            "gift_name": g.gift_name,
            "unit": g.unit,
            "stock_qty": float(g.stock_qty),
            "qty_per_ton": float(g.qty_per_ton),
            "dead_stock_qty": float(g.dead_stock_qty or 0),
            "gift_image_url": g.gift_image_url,
            "team": g.team,
        }
        for g in gifts
    ]


@router.get("/{promo_id}/shop-dispatch-status", response_model=list[dict])
def shop_dispatch_status(promo_id: int, db: Session = Depends(get_db)):
    """
    สรุปการแจกของแจกรายร้าน สำหรับโปรโมชันนี้
    - ดึง OrderPromotion ทั้งหมดของโปรโมชันนี้
    - รวม qty_given และ qty_dispatched ต่อ shop (customer)
    - รวม quantity_ton จาก SalesItem เพื่อคำนวณสิทธิ์
    """
    from sqlalchemy import func as sqlfunc

    promo = db.get(Promotion, promo_id)
    if not promo:
        raise HTTPException(404, "ไม่พบรายการส่งเสริมการขาย")

    # รวม op_id, order_id, gift_name, qty_given ต่อ order
    ops = (
        db.query(OrderPromotion)
        .filter(OrderPromotion.promotion_id == promo_id)
        .all()
    )

    if not ops:
        return []

    # Build per-shop summary
    shop_map = {}
    for op in ops:
        order = db.get(Sales, op.order_id)
        if not order:
            continue
        customer = db.get(Customer, order.customer_id)
        shop_name = customer.company_name if customer else op.order_id
        region = ""  # frontend maps region from SHOP_MASTER

        # sum tons from order items
        total_ton = db.query(sqlfunc.sum(OrderItem.quantity_ton)).filter(
            OrderItem.order_id == op.order_id
        ).scalar() or 0

        qty_dispatched = sum(float(d.qty_dispatched) for d in op.dispatches)

        key = shop_name
        if key not in shop_map:
            shop_map[key] = {
                "shop_name": shop_name,
                "region": region,
                "total_ton": 0.0,
                "qty_given": 0.0,
                "qty_dispatched": 0.0,
                "orders": [],
            }
        shop_map[key]["total_ton"] += float(total_ton)
        shop_map[key]["qty_given"] += float(op.qty_given)
        shop_map[key]["qty_dispatched"] += qty_dispatched
        shop_map[key]["orders"].append(op.order_id)

    result = []
    for s in shop_map.values():
        s["qty_remaining"] = s["qty_given"] - s["qty_dispatched"]
        result.append(s)

    # sort by region then shop_name
    REGION_ORDER = {"อีสานตอนบน":1,"อีสานตอนล่าง":2,"ตะวันออก":3,"กลาง":4,"เหนือ":5,"ใต้":6}
    result.sort(key=lambda x: (REGION_ORDER.get(x["region"], 99), x["shop_name"]))
    return result


# ---------------------------------------------------------------------------
# Import historical dispatch records from Excel
# ---------------------------------------------------------------------------

class HistoricalDispatch(BaseModel):
    dispatch_date: Optional[date] = None
    shop_name: Optional[str] = None
    qty_dispatched: Decimal
    remark: Optional[str] = None
    dispatch_type: str = "dispatch"
    salesperson_name: Optional[str] = None

class HistoricalGift(BaseModel):
    gift_name: str
    current_stock: Decimal = Decimal("0")
    dispatches: list[HistoricalDispatch] = []

class ImportHistoryPayload(BaseModel):
    gifts: list[HistoricalGift]
    promo_name: str = "ประวัติของแจก ปี 2568-2569"

@router.post("/import-history", status_code=201)
def import_history(payload: ImportHistoryPayload, db: Session = Depends(get_db)):
    """
    นำเข้าประวัติการแจกของแจกจาก Excel
    - สร้างโปรโมชัน "ประวัติของแจก" ถ้ายังไม่มี
    - สร้าง promotion_gifts + gift_dispatches
    - ตั้ง stock_qty = current_stock ที่ส่งมา
    """
    # find or create history promotion
    promo = db.query(Promotion).filter(Promotion.promo_name == payload.promo_name).first()
    if not promo:
        promo = Promotion(
            promo_name=payload.promo_name,
            is_active=False,
            notes="นำเข้าจาก Excel ประวัติการแจกของแถม",
        )
        db.add(promo)
        db.flush()

    gifts_created = 0
    dispatches_created = 0
    skipped_gifts = []

    for g in payload.gifts:
        # check if gift already exists under this promo
        existing = db.query(PromotionGift).filter(
            PromotionGift.promotion_id == promo.promotion_id,
            PromotionGift.gift_name == g.gift_name,
        ).first()

        if existing:
            # update stock only
            existing.stock_qty = g.current_stock
            gift_obj = existing
            skipped_gifts.append(g.gift_name)
        else:
            gift_obj = PromotionGift(
                promotion_id=promo.promotion_id,
                gift_name=g.gift_name,
                unit="ชิ้น",
                stock_qty=g.current_stock,
                qty_per_ton=Decimal("0"),
                dead_stock_qty=Decimal("0"),
            )
            db.add(gift_obj)
            db.flush()
            gifts_created += 1

        for d in g.dispatches:
            disp = GiftDispatch(
                gift_id=gift_obj.gift_id,
                op_id=None,
                dispatch_date=d.dispatch_date or date.today(),
                qty_dispatched=d.qty_dispatched,
                shop_name=d.shop_name,
                dispatch_type=d.dispatch_type,
                salesperson_name=d.salesperson_name,
                notes=d.remark,
                dispatched_by="นำเข้าจาก Excel",
            )
            db.add(disp)
            dispatches_created += 1

    db.commit()
    return {
        "status": "ok",
        "promotion_id": promo.promotion_id,
        "gifts_created": gifts_created,
        "gifts_updated": len(skipped_gifts),
        "dispatches_created": dispatches_created,
    }
