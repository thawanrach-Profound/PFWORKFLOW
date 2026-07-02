from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crm import RawMaterial
from app.schemas.crm import MaterialOut, MaterialUpdate

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("", response_model=list[MaterialOut])
def list_materials(low_stock_only: bool = False, db: Session = Depends(get_db)):
    mats = db.query(RawMaterial).order_by(RawMaterial.material_name).all()
    result = [MaterialOut.from_orm_with_alert(m) for m in mats]
    if low_stock_only:
        result = [r for r in result if r.low_stock]
    return result


@router.get("/alerts")
def stock_alerts(db: Session = Depends(get_db)):
    """วัตถุดิบที่ต่ำกว่า minimum_qty — สำหรับแจ้งเตือนทีมคลัง"""
    mats = db.query(RawMaterial).filter(RawMaterial.stock_qty < RawMaterial.minimum_qty).all()
    return [{"material_name": m.material_name, "stock_qty": float(m.stock_qty), "minimum_qty": float(m.minimum_qty)} for m in mats]


@router.put("/{material_id}", response_model=MaterialOut)
def update_material(material_id: int, payload: MaterialUpdate, db: Session = Depends(get_db)):
    m = db.get(RawMaterial, material_id)
    if not m:
        raise HTTPException(404, "ไม่พบวัตถุดิบ")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit(); db.refresh(m)
    return MaterialOut.from_orm_with_alert(m)
