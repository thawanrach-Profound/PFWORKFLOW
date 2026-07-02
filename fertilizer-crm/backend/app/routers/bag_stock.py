from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crm import BagItem, BagStockSession, BagStockEntry
from app.schemas.crm import (
    BagItemCreate, BagItemOut,
    BagStockSessionCreate, BagStockSessionOut, BagStockEntryOut
)

router = APIRouter(prefix="/api/bag-stock", tags=["bag-stock"])


# ── Bag Items (master) ────────────────────────────────────────
@router.get("/items", response_model=list[BagItemOut])
def list_bag_items(db: Session = Depends(get_db)):
    return db.query(BagItem).filter(BagItem.is_active == True).order_by(BagItem.item_code).all()


@router.post("/items", response_model=BagItemOut, status_code=201)
def create_bag_item(payload: BagItemCreate, db: Session = Depends(get_db)):
    if db.query(BagItem).filter(BagItem.item_code == payload.item_code).first():
        raise HTTPException(400, f"รหัส {payload.item_code} ซ้ำ")
    item = BagItem(**payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


# ── Bag Stock Sessions ────────────────────────────────────────
def _session_out(s: BagStockSession) -> BagStockSessionOut:
    out = BagStockSessionOut.model_validate(s)
    out.total_bags = sum(e.bag_count or 0 for e in s.entries)
    out.total_cost = sum(e.total_bag_cost or 0 for e in s.entries)
    return out


@router.get("", response_model=list[BagStockSessionOut])
def list_sessions(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    q = db.query(BagStockSession)
    if from_date: q = q.filter(BagStockSession.stock_date >= from_date)
    if to_date:   q = q.filter(BagStockSession.stock_date <= to_date)
    sessions = q.order_by(BagStockSession.stock_date.desc()).all()
    return [_session_out(s) for s in sessions]


@router.get("/{session_id}", response_model=BagStockSessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)):
    s = db.get(BagStockSession, session_id)
    if not s: raise HTTPException(404, "ไม่พบรอบตรวจนับ")
    return _session_out(s)


@router.post("", response_model=BagStockSessionOut, status_code=201)
def create_session(payload: BagStockSessionCreate, db: Session = Depends(get_db)):
    s = BagStockSession(
        stock_date=payload.stock_date,
        session_note=payload.session_note,
        created_by=payload.created_by,
    )
    db.add(s); db.flush()

    for e in payload.entries:
        # upsert bag_items master
        item = db.query(BagItem).filter(BagItem.item_code == e.item_code).first()
        if not item and e.item_code:
            item = BagItem(item_code=e.item_code, item_name=e.item_name)
            db.add(item); db.flush()
        entry = BagStockEntry(
            session_id=s.session_id,
            item_id=item.item_id if item else None,
            item_code=e.item_code,
            item_name=e.item_name,
            bag_count=e.bag_count,
            bag_price_unit=e.bag_price_unit,
            notes=e.notes,
        )
        db.add(entry)

    db.commit(); db.refresh(s)
    return _session_out(s)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    s = db.get(BagStockSession, session_id)
    if not s: raise HTTPException(404, "ไม่พบรอบตรวจนับ")
    db.delete(s); db.commit()


# ── Import Excel ──────────────────────────────────────────────
@router.post("/import", response_model=list[BagStockSessionOut], status_code=201)
async def import_bag_stock_excel(
    file_upload: bytes = None,
    db: Session = Depends(get_db),
):
    """Import Excel ไฟล์กระสอบ — แต่ละ Sheet = 1 session"""
    from fastapi import UploadFile, File
    raise HTTPException(501, "ใช้ endpoint /api/import/bag-stock แทน")
